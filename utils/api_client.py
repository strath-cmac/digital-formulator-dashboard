"""Centralised HTTP client and API discovery helpers for the dashboard."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

TIMEOUT_SHORT: int = 30
TIMEOUT_MEDIUM: int = 120
TIMEOUT_LONG: int = 900
OPENAPI_TIMEOUT: int = 8

_SESSION = requests.Session()
_RESOLVED_BASE_URL: Optional[str] = None
_LAST_OPTIONS: Dict[str, Any] = {}
_COMPONENTS_CACHE: Dict[str, Dict[str, str]] = {}

_DEFAULT_FALLBACK_OPTIONS: Dict[str, Any] = {
    "available_components": [],
    "available_apis": [],
    "available_excipients": [],
    "available_objectives": [],
    "available_constraints": [],
    "component_names": {},
    "current_defaults": {},
    "options_degraded": True,
}


def _normalise_url(url: str) -> str:
    return url.strip().rstrip("/")


def _dedupe(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        clean = _normalise_url(value)
        if clean and clean not in seen:
            ordered.append(clean)
            seen.add(clean)
    return ordered


def _candidate_base_urls() -> List[str]:
    env_url = os.getenv("API_BASE_URL", "")
    extra = os.getenv("API_BASE_URL_CANDIDATES", "")
    extras = [item for item in extra.split(",") if item.strip()]
    return _dedupe(
        [
            env_url,
            *extras,
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://host.docker.internal:8080",
            "http://host.docker.internal:8000",
        ]
    )


def _coerce_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _coerce_string_dict(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if str(key).strip()}


def _dedupe_ids(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def _safe_base_url() -> str:
    try:
        return get_base_url()
    except Exception:
        return _normalise_url(os.getenv("API_BASE_URL", ""))


def _probe_openapi(base_url: str) -> Dict[str, Any]:
    response = _SESSION.get(f"{base_url}/openapi.json", timeout=OPENAPI_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _resolve_base_url(force_refresh: bool = False) -> str:
    global _RESOLVED_BASE_URL

    if _RESOLVED_BASE_URL and not force_refresh:
        return _RESOLVED_BASE_URL

    errors: List[str] = []
    for candidate in _candidate_base_urls():
        try:
            _probe_openapi(candidate)
            _RESOLVED_BASE_URL = candidate
            return candidate
        except requests.RequestException as exc:
            errors.append(f"{candidate} ({exc.__class__.__name__})")

    preferred = _normalise_url(os.getenv("API_BASE_URL", "http://localhost:8080"))
    if preferred:
        _RESOLVED_BASE_URL = preferred
    if errors:
        raise requests.ConnectionError(
            "Unable to discover a reachable backend. Tried: " + ", ".join(errors)
        )
    raise requests.ConnectionError("Unable to discover a reachable backend.")


def get_base_url(force_refresh: bool = False) -> str:
    return _resolve_base_url(force_refresh=force_refresh)


@lru_cache(maxsize=8)
def _cached_openapi(base_url: str) -> Dict[str, Any]:
    return _probe_openapi(base_url)


def get_openapi(force_refresh: bool = False) -> Dict[str, Any]:
    base_url = get_base_url(force_refresh=force_refresh)
    if force_refresh:
        _cached_openapi.cache_clear()
    return _cached_openapi(base_url)


def get_api_contract(force_refresh: bool = False) -> Dict[str, Any]:
    schema = get_openapi(force_refresh=force_refresh)
    info = schema.get("info", {})
    paths = schema.get("paths", {})
    return {
        "base_url": get_base_url(force_refresh=force_refresh),
        "title": info.get("title", "Digital Formulator API"),
        "version": info.get("version", "unknown"),
        "path_map": paths,
        "paths": sorted(paths.keys()),
    }


def supports_endpoint(endpoint: str) -> bool:
    try:
        return endpoint in get_api_contract().get("path_map", {})
    except Exception:
        return False


def get_components(force_refresh: bool = False) -> Dict[str, Dict[str, str]]:
    if _COMPONENTS_CACHE and not force_refresh:
        return _COMPONENTS_CACHE

    registry: Dict[str, Dict[str, str]] = {"all": {}, "apis": {}, "excipients": {}}
    try:
        raw = _get("/components", timeout=TIMEOUT_MEDIUM)
        registry["all"] = _coerce_string_dict(raw.get("all"))
        registry["apis"] = _coerce_string_dict(raw.get("apis"))
        registry["excipients"] = _coerce_string_dict(raw.get("excipients"))
    except Exception:
        registry = {"all": {}, "apis": {}, "excipients": {}}

    if not registry["all"]:
        registry["all"] = {**registry["excipients"], **registry["apis"]}

    if not registry["excipients"] and registry["all"]:
        api_ids = set(registry["apis"])
        registry["excipients"] = {
            component_id: label
            for component_id, label in registry["all"].items()
            if component_id not in api_ids
        }

    _COMPONENTS_CACHE.clear()
    _COMPONENTS_CACHE.update(registry)
    return _COMPONENTS_CACHE


def _request(method: str, endpoint: str, timeout: int, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base_url = get_base_url()
    response = _SESSION.request(
        method=method,
        url=f"{base_url}{endpoint}",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    if not response.content:
        return {}
    return response.json()


def _get(endpoint: str, timeout: int = TIMEOUT_SHORT) -> Dict[str, Any]:
    return _request("GET", endpoint, timeout=timeout)


def _post(endpoint: str, payload: Dict[str, Any], timeout: int = TIMEOUT_SHORT) -> Dict[str, Any]:
    return _request("POST", endpoint, timeout=timeout, payload=payload)


def _normalise_options(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    global _LAST_OPTIONS

    data = raw or {}
    try:
        registry = get_components()
    except Exception:
        registry = {"all": {}, "apis": {}, "excipients": {}}

    registry_all = registry.get("all", {})
    registry_apis = registry.get("apis", {})
    registry_excipients = registry.get("excipients", {})

    component_names = {
        **dict(registry_all),
        **_coerce_string_dict(data.get("component_names")),
    }

    available_components = _coerce_string_list(data.get("available_components"))
    if not available_components:
        available_components = _coerce_string_list(data.get("available_materials"))
    if not available_components:
        available_components = _coerce_string_list(data.get("available_excipients"))
    if not available_components and registry_all:
        available_components = list(registry_all.keys())

    available_apis = _coerce_string_list(data.get("available_apis"))
    if not available_apis and registry_apis:
        available_apis = list(registry_apis.keys())

    available_excipients = _coerce_string_list(data.get("available_excipients"))
    if not available_excipients and registry_excipients:
        available_excipients = list(registry_excipients.keys())

    available_components = _dedupe_ids([*available_components, *available_apis, *available_excipients])
    if not available_components and registry_all:
        available_components = list(registry_all.keys())

    if available_components:
        component_id_set = set(available_components)
        available_apis = [cid for cid in available_apis if cid in component_id_set]
        available_excipients = [cid for cid in available_excipients if cid in component_id_set]

    if available_components and not available_excipients:
        if registry_excipients:
            available_excipients = [cid for cid in registry_excipients if cid in set(available_components)]
        else:
            api_ids = set(available_apis)
            available_excipients = [cid for cid in available_components if cid not in api_ids]

    current_defaults = data.get("current_defaults")
    if not isinstance(current_defaults, dict):
        current_defaults = {}

    normalised = {
        "available_components": available_components,
        "available_apis": [cid for cid in available_apis if cid in available_components] if available_components else available_apis,
        "available_excipients": available_excipients,
        "available_objectives": _coerce_string_list(data.get("available_objectives")),
        "available_constraints": _coerce_string_list(data.get("available_constraints")),
        "component_names": {str(key): str(value) for key, value in component_names.items()},
        "current_defaults": current_defaults,
        "options_degraded": bool(data.get("options_degraded", False)),
        "source_base_url": _safe_base_url(),
    }
    _LAST_OPTIONS = normalised
    return normalised


def health_check(force_refresh: bool = False) -> Tuple[bool, str]:
    try:
        contract = get_api_contract(force_refresh=force_refresh)
    except Exception as exc:
        return False, str(exc)

    path_count = len(contract.get("paths", []))
    return True, f"Connected to {contract['base_url']} with {path_count} API paths"


def get_options(force_refresh: bool = False) -> Dict[str, Any]:
    if force_refresh:
        _cached_openapi.cache_clear()

    try:
        raw = _get("/digital_formulator/options")
        return _normalise_options(raw)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code >= 500:
            fallback = dict(_DEFAULT_FALLBACK_OPTIONS)
            fallback["source_base_url"] = get_base_url()
            return _normalise_options(fallback)
        raise
    except Exception:
        fallback = dict(_DEFAULT_FALLBACK_OPTIONS)
        try:
            fallback["source_base_url"] = get_base_url()
        except Exception:
            pass
        return _normalise_options(fallback)


def component_label(cid: str, options: Optional[Dict[str, Any]] = None) -> str:
    names = (options or _LAST_OPTIONS).get("component_names", {})
    return names.get(cid, cid)


def component_short_name(cid: str) -> str:
    return cid


def is_api(cid: str, options: Optional[Dict[str, Any]] = None) -> bool:
    return cid in set((options or _LAST_OPTIONS).get("available_apis", []))


def get_component_choices(options: Optional[Dict[str, Any]] = None) -> List[str]:
    source = options or _LAST_OPTIONS
    return source.get("available_components") or source.get("available_excipients", [])


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


_FALLBACK_OPTIONS = _DEFAULT_FALLBACK_OPTIONS
