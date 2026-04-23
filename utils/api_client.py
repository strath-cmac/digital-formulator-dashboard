"""
Centralised HTTP client for the Digital Formulator FastAPI backend.

All network calls go through this module so the rest of the dashboard
never imports `requests` directly.  The API base URL is resolved once
at import time from the environment variable ``API_BASE_URL``
(default: http://localhost:8080).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8080").rstrip("/")

# Timeout constants (seconds)
TIMEOUT_SHORT: int = 30
TIMEOUT_MEDIUM: int = 120
TIMEOUT_LONG: int = 900   # optimiser can run for many minutes

# ── Component display labels ────────────────────────────────────────────
# Hardcoded fallback — the FastAPI /options endpoint only returns IDs.
KNOWN_COMPONENT_LABELS: Dict[str, str] = {
    "cc1":  "Croscarmellose Sodium",
    "ms1":  "Magnesium Stearate",
    "la3":  "Lactose (Lactohale LH300)",
    "la4":  "Lactose (Respitose SV003)",
    "la6":  "Lactose (SuperTab 14SD)",
    "la8":  "Lactose (Pharmatose 450M)",
    "la9":  "Lactose (SuperTab 30SD)",
    "la10": "Lactose (Tablettose 100)",
    "ma1":  "Mannitol (Pearlitol 200SD)",
    "mc5":  "MCC (Avicel PH101)",
    "mc6":  "MCC (Avicel PH102)",
    "mc7":  "MCC (Avicel PH200)",
    "sh14": "HPMC (Pharmacoat 603)",
    "sh15": "HPMC (Methocel K4M)",
    "sh16": "HPMC",
    "dm1":  "Dexamethasone",
}


def component_label(cid: str) -> str:
    """Return a human-readable label for a component ID."""
    name = KNOWN_COMPONENT_LABELS.get(cid)
    return f"{name} ({cid})" if name else cid


def component_short_name(cid: str) -> str:
    """Return only the name portion (without the ID suffix)."""
    return KNOWN_COMPONENT_LABELS.get(cid, cid)


# ── Internal helpers ────────────────────────────────────────────────────

def _get(endpoint: str, timeout: int = TIMEOUT_SHORT) -> Dict:
    r = requests.get(f"{BASE_URL}{endpoint}", timeout=timeout)
    r.raise_for_status()
    return r.json()


def _post(endpoint: str, payload: Dict, timeout: int = TIMEOUT_SHORT) -> Dict:
    r = requests.post(f"{BASE_URL}{endpoint}", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ── Public API ──────────────────────────────────────────────────────────

def health_check() -> Tuple[bool, str]:
    """Ping the options endpoint; return (ok, message)."""
    try:
        _get("/digital_formulator/options", timeout=10)
        return True, "Connected"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to API — is it running?"
    except requests.exceptions.Timeout:
        return False, "API timed out"
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP error: {e}"
    except Exception as e:
        return False, str(e)


def get_options() -> Dict:
    """
    GET /digital_formulator/options
    Returns available objectives, constraints, excipients and current defaults.
    """
    return _get("/digital_formulator/options")


def single_run(
    titles: List[str],
    components: List[str],
    fractions: List[float],
    cp: float,
) -> Dict:
    """POST /single_run — single-point simulation at a fixed compaction pressure."""
    return _post(
        "/single_run",
        {"titles": titles, "components": components, "fractions": fractions, "cp": cp},
    )


def multiple_run(
    titles: List[str],
    components: List[str],
    fractions: List[float],
    cp_range: Tuple[float, float],
    n_runs: int,
) -> Dict:
    """
    POST /multiple_run — Kawakita + Duckworth empirical models across a CP range.
    Returns compressibility profile DataFrame in ``results_df`` key.
    """
    return _post(
        "/multiple_run",
        {
            "titles": titles,
            "components": components,
            "fractions": fractions,
            "cp_range": list(cp_range),
            "n_runs": n_runs,
        },
        timeout=TIMEOUT_MEDIUM,
    )


def digital_formulator(
    cmac_id: str,
    drug_loading: float,
    objectives: Optional[List[str]] = None,
    constraints: Optional[List[Dict]] = None,
    api_fraction_variable: bool = True,
    api_fraction_bounds: Optional[Tuple[float, float]] = None,
    disintegrant_id: str = "cc1",
    disintegrant_fraction: float = 0.08,
    lubricant_id: str = "ms1",
    lubricant_fraction: float = 0.01,
    excipient_options: Optional[List[str]] = None,
    filler1_fraction_lower: float = 0.0,
    cp_bounds: Tuple[float, float] = (70.0, 250.0),
    pop_size: int = 20,
    n_iters: int = 50,
    n_threads: int = 8,
    seed: int = 1,
) -> Dict:
    """POST /digital_formulator — run in-silico formulation optimisation."""
    payload: Dict[str, Any] = {
        "cmac_id": cmac_id,
        "drug_loading": drug_loading,
        "api_fraction_variable": api_fraction_variable,
        "disintegrant_id": disintegrant_id,
        "disintegrant_fraction": disintegrant_fraction,
        "lubricant_id": lubricant_id,
        "lubricant_fraction": lubricant_fraction,
        "filler1_fraction_lower": filler1_fraction_lower,
        "cp_bounds": list(cp_bounds),
        "pop_size": pop_size,
        "n_iters": n_iters,
        "n_threads": n_threads,
        "seed": seed,
    }
    if objectives is not None:
        payload["objectives"] = objectives
    if constraints is not None:
        payload["constraints"] = constraints
    if api_fraction_bounds is not None:
        payload["api_fraction_bounds"] = list(api_fraction_bounds)
    if excipient_options is not None:
        payload["excipient_options"] = excipient_options

    return _post("/digital_formulator", payload, timeout=TIMEOUT_LONG)
