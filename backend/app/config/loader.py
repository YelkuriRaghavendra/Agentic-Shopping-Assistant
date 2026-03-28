"""
Config loader.

Loads JSON config files from app/config/ at startup.
Values are cached — edit JSON files and restart to apply.

Usage:
    from app.config.loader import business_rules
    max_brands = business_rules["session"]["max_profile_brands"]
"""

import json
from functools import lru_cache
from pathlib import Path

_CONFIG_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def _load(filename: str) -> dict:
    path = _CONFIG_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def business_rules() -> dict:
    return _load("business_rules.json")


@lru_cache(maxsize=1)
def prompts() -> dict:
    return _load("prompts.json")
