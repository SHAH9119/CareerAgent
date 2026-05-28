import copy
import json
import os
from functools import lru_cache

DEFAULT_PATH = os.path.join("config", "domain_config.default.json")


def _deep_merge(base: dict, override: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=8)
def _load_file(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_domain_config(profile: dict | None = None, explicit_path: str | None = None) -> dict:
    """Load domain rules from default file, optional path, and profile overrides."""
    base = _load_file(DEFAULT_PATH)

    path = explicit_path or (profile or {}).get("domain_config_path")
    if path:
        base = _deep_merge(base, _load_file(path))

    inline = (profile or {}).get("domain_config")
    if inline:
        base = _deep_merge(base, inline)

    return base


def clear_domain_config_cache() -> None:
    _load_file.cache_clear()
