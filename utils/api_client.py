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

BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

# Timeout constants (seconds)
TIMEOUT_SHORT: int = 30
TIMEOUT_MEDIUM: int = 120
TIMEOUT_LONG: int = 900   # optimiser can run for many minutes

# ── Fallback options ────────────────────────────────────────────────────
# Used when /digital_formulator/options returns 5xx.
# Component lists are intentionally empty — the dashboard will show an
# error banner if the API is unreachable rather than misleading stale data.
_FALLBACK_OPTIONS: Dict = {
    "available_apis":        [],
    "available_excipients":  [],
    "available_objectives":  [
        "maximise_tensile",
        "minimise_tablet_weight",
        "maximise_porosity",
        "maximise_ffc",
        "minimise_eaoif",
    ],
    "available_constraints": [
        "eaoif_max",
        "ffc_min",
        "porosity_min",
        "porosity_minus_std_min",
        "tensile_mean_min",
        "tensile_strength_min",
    ],
    "component_names": {},
    "current_defaults": {
        "objectives":             ["maximise_tensile", "minimise_tablet_weight"],
        "constraints":            [
            {"name": "porosity_minus_std_min", "threshold": 0.14},
            {"name": "ffc_min",                "threshold": 4.0},
            {"name": "tensile_strength_min",   "threshold": 2.0},
            {"name": "eaoif_max",              "threshold": 41.0},
        ],
        "excipient_options":      [],
        "disintegrant_id":        "cc1",
        "disintegrant_fraction":  0.08,
        "lubricant_id":           "ms1",
        "lubricant_fraction":     0.01,
        "cp_bounds":              [70.0, 250.0],
        "filler1_fraction_lower": 0.0,
        "pop_size":               20,
        "n_iters":                50,
        "n_threads":              8,
    },
}

# ── Process-level component name cache ─────────────────────────────────
# Populated on first call to get_components() and reused for the
# lifetime of the Streamlit worker process.
_COMP_CACHE: Dict[str, Any] = {}


def component_label(cid: str) -> str:
    """Return a human-readable label for a component ID.

    APIs are tagged with '[API]' so they are visually distinct from excipients
    in every formulation builder dropdown.
    """
    comp = get_components()
    name = comp["all"].get(cid, cid)
    tag = " [API]" if cid in comp["apis"] else ""
    return f"{name}{tag} ({cid})"


def component_short_name(cid: str) -> str:
    """Return only the name portion (without the ID suffix)."""
    return get_components()["all"].get(cid, cid)


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

def get_components() -> Dict[str, Dict[str, str]]:
    """
    GET /components — returns component registry with APIs and excipients.

    Response shape::

        {
            "all":        {id: name, ...},   # every material in df_raw
            "apis":       {id: name, ...},   # valid API IDs for the formulator
            "excipients": {id: name, ...},   # non-API materials
        }

    Cached at the process level so the network call is made at most once
    per Streamlit worker process.
    """
    if not _COMP_CACHE:
        try:
            result = _get("/components", timeout=TIMEOUT_MEDIUM)
        except Exception:
            result = {"all": {}, "apis": {}, "excipients": {}}
        _COMP_CACHE.update(result)
    return _COMP_CACHE


def get_dataframe(name: str) -> Dict:
    """
    GET /data/{name} — retrieve one of the seven core datasets as JSON.

    Valid names: df_raw, df_blend, df_tablet, psd_raw, psd_blend, ar_raw, ar_blend

    - Tabular datasets (df_raw, df_blend, df_tablet) → list of row dicts
    - Matrix datasets (psd_raw, psd_blend, ar_raw, ar_blend) → column dict
    """
    return _get(f"/data/{name}", timeout=TIMEOUT_MEDIUM)


def health_check() -> Tuple[bool, str]:
    """Verify the API is reachable by fetching /openapi.json (always available).

    /digital_formulator/options is NOT used here because it can return 5xx
    while all simulation endpoints are working fine.
    """
    url = f"{BASE_URL}/openapi.json"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return True, "Connected"
    except requests.exceptions.ConnectionError:
        return False, (
            f"Connection refused — cannot reach {BASE_URL}\n"
            "If the API is running on the **same machine** as Docker, use "
            "`--network=host` (Linux) or `http://host.docker.internal:8000` (Docker Desktop)."
        )
    except requests.exceptions.Timeout:
        return False, f"Request timed out after 10 s — {url}"
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP {e.response.status_code} from {url} — {e}"
    except Exception as e:
        return False, f"{url} — {e}"


def get_options() -> Dict:
    """
    GET /digital_formulator/options

    Returns available objectives, constraints, excipients, APIs, component
    names, and current defaults.  If the endpoint returns a 5xx error,
    silently falls back to minimal defaults so the dashboard remains usable.
    """
    try:
        return _get("/digital_formulator/options")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code >= 500:
            return _FALLBACK_OPTIONS
        raise
    except Exception:
        return _FALLBACK_OPTIONS


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


def multiple_run_syn_api(
    titles: List[str],
    components: List[str],
    fractions: List[float],
    cp_range: Tuple[float, float],
    n_runs: int,
    api_psd: List[float],
) -> Dict:
    """
    POST /multiple_run_syn_api

    Kawakita + Duckworth empirical models with a user-supplied synthetic API PSD.
    Useful for in-silico exploration of novel APIs not yet in the training database.
    """
    return _post(
        "/multiple_run_syn_api",
        {
            "titles":     titles,
            "components": components,
            "fractions":  fractions,
            "cp_range":   list(cp_range),
            "n_runs":     n_runs,
            "api_psd":    api_psd,
        },
        timeout=TIMEOUT_MEDIUM,
    )


def ffc_v3(
    titles: List[str],
    components: List[str],
    fractions: List[float],
) -> Optional[float]:
    """
    POST /ffc_new — 2nd-generation FFC regression model (v3).

    Returns the predicted FFC value, or ``None`` if the endpoint is
    unavailable (e.g. model not loaded on the server).
    """
    try:
        res = _post(
            "/ffc_new",
            {"titles": titles, "components": components, "fractions": fractions},
        )
        val = res.get("ffc_new")
        return float(val) if val is not None else None
    except Exception:
        return None


def ffc_v4_class(
    titles: List[str],
    components: List[str],
    fractions: List[float],
) -> Optional[str]:
    """
    POST /ffc_class — FFC classification label from the v4 model.

    Returns a string label (e.g. ``"Easy-flowing"``) or ``None`` if
    the endpoint is unavailable.
    """
    try:
        res = _post(
            "/ffc_class",
            {"titles": titles, "components": components, "fractions": fractions},
        )
        return res.get("ffc_class")
    except Exception:
        return None
