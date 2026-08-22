"""
Centralised application settings loaded from environment variables / .env file.

All configuration is accessed through the `get_settings()` helper, which returns
a cached singleton `Settings` instance.  Use dependency injection (FastAPI Depends)
in route handlers rather than importing get_settings() directly in service code.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration.

    Values are read from environment variables (case-insensitive) and can be
    overridden by a `.env` file in the project root.  See `.env.example` for
    all supported keys and their documentation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # LLM Provider
    # ------------------------------------------------------------------
    llm_provider: Literal["groq", "ollama", "mock"] = Field(
        default="mock",
        description="Which LLM backend to use.",
    )
    llm_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Model name for the selected provider.",
    )
    llm_timeout_seconds: float = Field(
        default=3.5,
        ge=0.5,
        le=30.0,
        description="Hard timeout for a single LLM API call in seconds.",
    )

    # ------------------------------------------------------------------
    # Provider API Keys
    # ------------------------------------------------------------------
    groq_api_key: str = Field(
        default="",
        description="Groq API key (required when llm_provider=groq).",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server base URL (required when llm_provider=ollama).",
    )

    # ------------------------------------------------------------------
    # Recommendation Engine Limits
    # ------------------------------------------------------------------
    max_candidates: int = Field(
        default=20,
        ge=5,
        le=50,
        description="Maximum number of restaurant candidates passed to the LLM.",
    )
    max_recommendations: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of recommendations returned in the response.",
    )

    # ------------------------------------------------------------------
    # Data / Cache
    # ------------------------------------------------------------------
    cache_dir: str = Field(
        default="data/cache",
        description="Directory for preprocessed dataset cache (relative to project root).",
    )
    hf_dataset_id: str = Field(
        default="ManikaSaini/zomato-restaurant-recommendation",
        description="Hugging Face dataset identifier.",
    )

    # ------------------------------------------------------------------
    # API Server
    # ------------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1024, le=65535)
    ui_port: int = Field(default=8501, ge=1024, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("groq_api_key", mode="after")
    @classmethod
    def warn_missing_groq_key(cls, v: str, info) -> str:
        """Warn at settings-load time if the key is absent but provider is groq."""
        return v

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalise_provider(cls, v: str) -> str:
        return v.lower().strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Using lru_cache ensures the .env file is read only once per process.
    Call ``get_settings.cache_clear()`` in tests to reload settings.
    """
    return Settings()
