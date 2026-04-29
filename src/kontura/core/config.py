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
        default="postgresql+asyncpg://kontura:dev_local_password@localhost:5433/kontura",
        description="Async-PostgreSQL-Connection-String (asyncpg-Treiber)",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis-Connection-String fuer Cache und Queues",
    )

    # ==========================================
    # KI-Provider
    # ==========================================
    ai_provider: str = Field(default="openai", description="openai | azure | ollama")

    # OpenAI (direkt)
    openai_api_key: str = Field(default="", description="OpenAI API Key (leer im Test/CI)")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI Embedding-Modell (1536 Dim, billig, schnell)",
    )
    openai_chat_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI Chat-Modell (Dev: mini, Production spaeter: gpt-4o)",
    )

    # ==========================================
    # JWT / Auth
    # ==========================================
    # WICHTIG: jwt_secret MUSS in Production aus ENV kommen, NICHT der Default!
    # Generierung: python -c "import secrets; print(secrets.token_urlsafe(48))"
    # In Production: mindestens 32 Bytes (256 Bit) Entropie.
    jwt_secret: str = Field(
        default="dev-only-change-me-in-production-via-env-variable-please",
        description="HS256-Secret fuer JWT-Signing. In Prod aus ENV setzen!",
        min_length=32,
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT-Signaturalgorithmus")
    jwt_ttl_minutes: int = Field(
        default=60 * 24,
        ge=1,
        description="Token-Gueltigkeit in Minuten (Default: 24h)",
    )


settings = Settings()
