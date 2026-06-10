# core/config.py
import secrets
from functools import lru_cache

from pydantic import field_validator
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
    PROTHEUS_HTTP_RETRY_ATTEMPTS: int = 5
    PROTHEUS_HTTP_RETRY_BACKOFF_SECONDS: float = 15.0

    # Redis / RQ
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage (S3-compatible - Railway Bucket Storage)
    STORAGE_ENDPOINT: str = ""
    STORAGE_ACCESS_KEY_ID: str = ""
    STORAGE_SECRET_ACCESS_KEY: str = ""
    STORAGE_REGION: str = "auto"
    STORAGE_BUCKET: str = ""

    # Certificado Digital
    CERT_ENCRYPTION_KEY: str = ""

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Retorna instancia cacheada das configuracoes."""
    return Settings()


settings = get_settings()
