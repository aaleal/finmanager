from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Every value arrives from the environment."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: str = "production"
    log_level: str = "INFO"
    tz: str = "Europe/Lisbon"

    postgres_user: str = "finmanager"
    postgres_password: str = "finmanager"
    postgres_db: str = "finmanager"
    postgres_host: str = "db"
    postgres_port: int = 5432

    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "dev-only-secret-key"
    session_ttl_days: int = 30
    cookie_secure: bool = False

    storage_root: Path = Path("/var/lib/finmanager/storage")

    bootstrap_owner_email: str = "owner@finmanager.local"
    bootstrap_owner_password: str = "finmanager"
    bootstrap_household_name: str = "Casa"

    brickset_api_key: str = ""

    # Signed document URLs are short-lived by design (§1a Document).
    document_url_ttl_minutes: int = 15
    max_upload_bytes: int = 15 * 1024 * 1024

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
