"""
Application configuration.

All configurable values are read from environment variables (via a .env file
in local development). Nothing sensitive is hardcoded here — see
docs/DEPLOYMENT.md and .env.example.

Per RELIABILITY_AND_TRUST.md / AI_ARCHITECTURE.md: ANTHROPIC_API_KEY is
optional. If it is unset, the AI Reasoning Layer is skipped and the
deterministic fallback investigation engine is used instead. The
application must be fully usable with this key unset.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings, loaded once and cached."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---
    env: str = "development"
    app_name: str = "EcoTwin API"

    # --- Database ---
    # Defaults to a local SQLite file so the backend can be run and tested
    # without a Postgres server present (e.g. in this sandbox / for quick
    # local dev). Production deployments should set DATABASE_URL to a
    # PostgreSQL connection string, per docs/DEPLOYMENT.md and
    # docs/TECH_STACK.md.
    database_url: str = "sqlite:///./ecotwin.db"

    # --- AI (optional) ---
    # If unset, the AI Reasoning Layer is disabled and the deterministic
    # fallback investigation engine is used for every investigation.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # --- Emission factor region (see docs/EMISSION_CALCULATIONS.md) ---
    emission_factor_region: str = "IN"

    # --- CORS ---
    # Comma-separated list of allowed frontend origins.
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @property
    def ai_enabled(self) -> bool:
        """Whether the AI Reasoning Layer should be attempted at all."""
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance (read once per process)."""
    return Settings()
