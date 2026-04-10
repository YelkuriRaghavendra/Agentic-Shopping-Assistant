"""Tests for config loader — verify all JSON configs load and have expected keys."""
import pytest

pytestmark = pytest.mark.unit


def test_business_rules_loads():
    from app.config.loader import business_rules
    br = business_rules()
    assert "budget" in br
    assert "session" in br
    assert "slot_extraction" in br


def test_prompts_loads():
    from app.config.loader import prompts
    p = prompts()
    assert "system" in p
    assert "skills" in p


def test_commerce_intents_loads():
    from app.config.loader import commerce_intents
    ci = commerce_intents()
    assert "intent_keywords" in ci
    assert "checkout_initiate" in ci["intent_keywords"]
    assert "required_slots" in ci
    assert "slot_prompts" in ci
    assert "purchase_intent_phrases" in ci
    assert "browse_category_words" in ci
    assert "self_signals" in ci
    assert "other_signals" in ci


def test_guardrails_config_loads():
    from app.config.loader import guardrails_config
    gc = guardrails_config()
    assert "injection_patterns" in gc
    assert "harmful_patterns" in gc
    assert "pii_patterns" in gc
    assert "intent_keywords" in gc
    assert "responses" in gc


def test_style_config_loads():
    from app.config.loader import style_config
    sc = style_config()
    assert "colour_pairings" in sc
    assert "colour_aliases" in sc
    assert "brand_size_notes" in sc
    assert "foot_type_advice" in sc


def test_search_config_loads():
    from app.config.loader import search_config
    sc = search_config()
    assert "defaults" in sc
    assert "per_tool" in sc
    assert sc["defaults"]["top_k"] == 5


def test_memory_config_loads():
    from app.config.loader import memory_config
    mc = memory_config()
    assert "history" in mc
    assert "session" in mc
    assert "profile" in mc
    assert "suggestions" in mc
    assert mc["history"]["token_budget"] == 800


def test_streaming_config_loads():
    from app.config.loader import streaming_config
    sc = streaming_config()
    assert "word_delay_seconds" in sc
    assert "heartbeat_interval_seconds" in sc


def test_agents_config_loads():
    from app.config.loader import agents_config
    ac = agents_config()
    assert "supervisor" in ac
    assert "shopping" in ac
    assert "checkout" in ac
    assert ac["supervisor"]["model_tier"] == "cheap"


def test_llm_config_loads():
    from app.config.loader import llm_config
    lc = llm_config()
    assert "provider" in lc
    assert "models" in lc
    assert "primary" in lc["models"]
    assert "cheap" in lc["models"]
