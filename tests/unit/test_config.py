"""
Unit tests for src/config.py — verifies Settings loads from env vars correctly.
"""
import os

import pytest


def test_settings_defaults():
    """Settings should load with sane defaults without any .env file."""
    from src.config import get_settings
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.llm_provider == "mock"
    assert settings.llm_model == "llama-3.3-70b-versatile"
    assert settings.max_candidates == 20
    assert settings.max_recommendations == 5
    assert 0.5 <= settings.llm_timeout_seconds <= 30.0


def test_settings_override_via_env(monkeypatch):
    """Environment variables should override default values."""
    from src.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test-key")
    monkeypatch.setenv("MAX_CANDIDATES", "15")

    # Re-import to pick up monkeypatched env
    import importlib
    import src.config as cfg_module
    importlib.reload(cfg_module)
    from src.config import get_settings as get_fresh

    get_fresh.cache_clear()
    settings = get_fresh()

    assert settings.llm_provider == "groq"
    assert settings.llm_model == "llama-3.3-70b-versatile"
    assert settings.groq_api_key == "gsk-test-key"
    assert settings.max_candidates == 15

    # Restore
    get_fresh.cache_clear()
    importlib.reload(cfg_module)


def test_invalid_llm_provider_raises():
    """An unrecognised LLM provider should raise a validation error."""
    from pydantic import ValidationError
    from src.config import Settings

    with pytest.raises(ValidationError):
        Settings(llm_provider="unknown_provider")


def test_max_candidates_bounds():
    """max_candidates must be within [5, 50]."""
    from pydantic import ValidationError
    from src.config import Settings

    with pytest.raises(ValidationError):
        Settings(max_candidates=1)   # below minimum

    with pytest.raises(ValidationError):
        Settings(max_candidates=100)  # above maximum
