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


@lru_cache(maxsize=1)
def commerce_intents() -> dict:
    return _load("commerce_intents.json")


@lru_cache(maxsize=1)
def guardrails_config() -> dict:
    return _load("guardrails.json")


@lru_cache(maxsize=1)
def style_config() -> dict:
    return _load("style_advisor.json")


@lru_cache(maxsize=1)
def search_config() -> dict:
    return _load("search.json")


@lru_cache(maxsize=1)
def memory_config() -> dict:
    return _load("memory.json")


@lru_cache(maxsize=1)
def streaming_config() -> dict:
    return _load("streaming.json")


@lru_cache(maxsize=1)
def agents_config() -> dict:
    return _load("agents.json")


@lru_cache(maxsize=1)
def llm_config() -> dict:
    return _load("llm.json")
