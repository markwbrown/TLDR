"""Configuration management using pydantic-settings."""

from __future__ import annotations

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    
    # Rate Limiting
    token_limit_per_minute: int = 180_000
    max_tokens_per_request: int = 4000
    response_buffer: int = 100
    context_buffer: int = 200

    # Gmail Labels
    gmail_source_label: str = "School"
    gmail_processed_label: str = "SchoolProcessed"

    # Email Settings
    to_email: str | None = None
    
    # API Settings (for FastAPI mode)
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str | None = None  # Optional API key for authentication

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
