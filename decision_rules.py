import json
from pathlib import Path


RULES_PATH = Path("model") / "decision_rules.json"

DEFAULT_RULES = {
    "npk": {
        "k_severe_high": 140.0,
        "n_severe_high": 150.0,
        "p_severe_low": 25.0,
        "k_pair_high": 120.0,
    },
    "confidence": {
        "favorable_min": 70.0,
        "non_favorable_uncertain_max": 55.0,
    },
}


_cache = None
_cache_mtime = None


def _deep_merge(base, custom):
    merged = dict(base)
    for key, value in custom.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_decision_rules(force_reload=False):
    global _cache, _cache_mtime

    if not RULES_PATH.exists():
        _cache = DEFAULT_RULES
        _cache_mtime = None
        return _cache

    mtime = RULES_PATH.stat().st_mtime
    if not force_reload and _cache is not None and _cache_mtime == mtime:
        return _cache

    with RULES_PATH.open("r", encoding="utf-8") as file:
        custom = json.load(file)

    _cache = _deep_merge(DEFAULT_RULES, custom)
    _cache_mtime = mtime
    return _cache


def save_decision_rules(rules):
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RULES_PATH.open("w", encoding="utf-8") as file:
        json.dump(rules, file, indent=2)
