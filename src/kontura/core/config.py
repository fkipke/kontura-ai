"""Zentrale Anwendungskonfiguration.

Alle Werte werden aus Umgebungsvariablen geladen (via .env im Dev-Betrieb).
Pydantic validiert Typen und meldet fehlende Werte beim App-Start.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Zentrale Konfiguration fuer Kontura AI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Anwendungsidentifikation
    app_name: str = Field(default="Kontura AI")
    app_env: str = Field(default="development", description="development | staging | production")
    app_version: str = Field(default="0.1.0")

    # HTTP-Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Logging
    log_level: str = Field(default="INFO")

    # Datenbank
    database_url: str = Field(
        default="postgresql+asyncpg://kontura:dev_local_password@localhost:5432/kontura",
        description="Async-PostgreSQL-Connection-String (asyncpg-Treiber)",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis-Connection-String fuer Cache und Queues",
    )


settings = Settings()