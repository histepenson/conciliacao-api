# core/config.py
import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuracoes da aplicacao."""

    # Aplicacao
    APP_NAME: str = "ConciliaAI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/conciliacao"

    # JWT
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 240  # 4 horas
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Password Reset
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Email SMTP
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "ConciliaAI"
    SMTP_FROM_EMAIL: str = "histepenson@smartconciliacoes.com.br"
    SMTP_USE_TLS: bool = True

    # URLs
    FRONTEND_URL: str = "http://localhost:3000"

    # Security
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True

    # Rate Limiting
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "https://dev.smartconciliacoes.com.br" ]

    # Protheus
    PROTHEUS_URL: str = ""
    PROTHEUS_USER: str = ""
    PROTHEUS_PASSWORD: str = ""
    PROTHEUS_TENANT: str = "02,0201"
    PROTHEUS_HTTP_TIMEOUT_SECONDS: float = 1800.0
    PROTHEUS_HTTP_RETRY_ATTEMPTS: int = 3
    PROTHEUS_HTTP_RETRY_BACKOFF_SECONDS: float = 2.0

    # Storage
    STORAGE_DIR: str = "data"

    # Certificado Digital
    CERT_ENCRYPTION_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Retorna instancia cacheada das configuracoes."""
    return Settings()


settings = get_settings()


def resolve_storage_dir() -> Path:
    """
    Resolve diretorio de storage com fallback seguro para Railway.

    Regras:
    - Se STORAGE_DIR estiver definido e diferente de "data", usa valor informado.
    - Se estiver em Railway e STORAGE_DIR estiver ausente ou "data", usa "/data".
    - Caso contrario, usa "data" (desenvolvimento local).
    """
    configured = os.environ.get("STORAGE_DIR", settings.STORAGE_DIR).strip()
    is_railway = os.environ.get("RAILWAY_ENVIRONMENT") is not None

    if is_railway and (not configured or configured == "data"):
        return Path("/data").resolve()

    return Path(configured or "data").resolve()
