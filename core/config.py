# core/config.py
import json
import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field, AliasChoices, field_validator
from pydantic_settings import BaseSettings, NoDecode

# Carrega o .env correto (.env.develop | .env) ANTES da classe Settings ser
# definida/instanciada. Nao pode depender de db.py ter sido importado
# primeiro para popular os.environ -- main.py importa core.config antes de
# qualquer router (e portanto antes de db.py), entao sem isso aqui o
# Settings() do lru_cache abaixo fica com um snapshot de ambiente
# incompleto (faltando tudo que so' existe no .env.develop) pelo resto do
# processo, independente do que rodar depois.
_BASE_DIR = Path(__file__).resolve().parent.parent
_APP_ENV = os.getenv("APP_ENV", "production")
_env_file = f".env.{_APP_ENV}" if _APP_ENV != "production" else ".env"
_env_path = _BASE_DIR / _env_file
if not _env_path.exists():
    _env_path = _BASE_DIR / ".env"
load_dotenv(dotenv_path=_env_path, override=True)


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
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000", "http://127.0.0.1:3000", "https://dev.smartconciliacoes.com.br" ]

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
    # Aceita tanto STORAGE_* quanto os nomes gerados pelo plugin de bucket do Railway
    STORAGE_ENDPOINT: str = Field(default="", validation_alias=AliasChoices("STORAGE_ENDPOINT", "ENDPOINT"))
    STORAGE_ACCESS_KEY_ID: str = Field(default="", validation_alias=AliasChoices("STORAGE_ACCESS_KEY_ID", "ACCESS_KEY_ID"))
    STORAGE_SECRET_ACCESS_KEY: str = Field(default="", validation_alias=AliasChoices("STORAGE_SECRET_ACCESS_KEY", "SECRET_ACCESS_KEY"))
    STORAGE_REGION: str = Field(default="auto", validation_alias=AliasChoices("STORAGE_REGION", "REGION"))
    STORAGE_BUCKET: str = Field(default="", validation_alias=AliasChoices("STORAGE_BUCKET", "BUCKET"))

    # Certificado Digital
    CERT_ENCRYPTION_KEY: str = ""

    # SmartConciliacoes IA (engine externa de matching/diagnostico de divergencias)
    SMARTCONCILIACOES_IA_URL: str = ""
    SMARTCONCILIACOES_IA_API_KEY: str = ""

    # Anthropic (extracao de dados de imagem - Conferencia LEASING, relatorios via print/OCR)
    ANTHROPIC_API_KEY: str = ""

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

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
