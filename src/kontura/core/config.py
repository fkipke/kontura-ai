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

    # ==========================================
    # Rate-Limiting (slowapi)
    # ==========================================
    # Im Test deaktivierbar via ENV (RATE_LIMIT_ENABLED=false), damit
    # bestehende Tests nicht durch Limits aus dem Tritt kommen.
    rate_limit_enabled: bool = Field(
        default=True,
        description="Master-Switch fuer Rate-Limiting (in Tests: false)",
    )

    # Pro-IP Limits (Brute-Force-Schutz fuer unauthentifizierte Endpoints)
    rate_limit_register_per_ip: str = Field(default="5/minute")
    rate_limit_login_per_ip: str = Field(default="10/minute")

    # Pro-Tenant Limits (authentifizierte Endpoints)
    rate_limit_default_per_tenant: str = Field(default="60/minute")
    rate_limit_llm_per_tenant: str = Field(default="20/minute")
    rate_limit_audit_per_tenant: str = Field(default="30/minute")

    # ==========================================
    # CORS (Cross-Origin Resource Sharing)
    # ==========================================
    # Welche Frontend-Origins duerfen die API aufrufen?
    # Im Dev: typische lokale Frontend-Ports (3000=Next.js, 5173=Vite).
    # In Production: NUR die echte Frontend-Domain (per ENV ueberschreiben).
    #
    # WICHTIG: Niemals "*" in Production - das oeffnet die API fuer JEDE Webseite!
    cors_allowed_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        description="Erlaubte Frontend-Origins (Komma-getrennt in ENV)",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="Cookies/Auth-Header bei Cross-Origin-Requests erlauben",
    )

    # ==========================================
    # Security-Headers (OWASP)
    # ==========================================
    # HSTS aktivieren wir nur in Production (im Dev ueber HTTP nervt's).
    enable_hsts: bool = Field(
        default=False,
        description="HTTP Strict Transport Security - in Production AN!",
    )


settings = Settings()
