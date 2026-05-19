"""Utilitários compartilhados para integração com o Protheus."""
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.config import settings
from models.empresa import Empresa


# ============================================================
# Criptografia de senha
# ============================================================

def _get_fernet() -> Optional[Fernet]:
    key = settings.CERT_ENCRYPTION_KEY
    if not key:
        return None
    raw = key.encode() if isinstance(key, str) else key
    return Fernet(raw)


def encrypt_password(plain: str) -> str:
    """Cifra a senha em texto puro usando CERT_ENCRYPTION_KEY."""
    f = _get_fernet()
    if not f:
        return plain
    return f.encrypt(plain.encode()).decode()


def decrypt_password(token: str) -> str:
    """Decifra senha armazenada. Retorna o token original se não conseguir."""
    f = _get_fernet()
    if not f:
        return token
    try:
        return f.decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return token


# ============================================================
# Config de conexão Protheus
# ============================================================

@dataclass
class ProtheusConfig:
    url: str
    rest_prefix: str
    user: str
    password: str
    tenant: str


def resolve_protheus_config(empresa_id: Optional[int], db: Optional[Session]) -> ProtheusConfig:
    """
    Resolve a configuração completa de conexão com o Protheus.

    Prioridade: campos da empresa (banco) → variáveis de ambiente (.env).
    """
    if empresa_id is not None and db is not None:
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if not empresa:
            raise HTTPException(status_code=404, detail=f"Empresa {empresa_id} nao encontrada")

        url = empresa.protheus_url or settings.PROTHEUS_URL
        if not url:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"A empresa '{empresa.nome}' nao possui URL do Protheus configurada. "
                    "Acesse Administracao > Empresas e informe a URL."
                ),
            )

        tenant = empresa.protheus_tenant or settings.PROTHEUS_TENANT
        if not tenant:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"A empresa '{empresa.nome}' nao possui Tenant ID do Protheus configurado. "
                    "Acesse Administracao > Empresas e informe o Tenant ID."
                ),
            )

        prefix = (empresa.protheus_rest_prefix or "rest").strip("/")
        user = empresa.protheus_user or settings.PROTHEUS_USER

        if empresa.protheus_password:
            password = decrypt_password(empresa.protheus_password)
        else:
            password = settings.PROTHEUS_PASSWORD

        return ProtheusConfig(url=url, rest_prefix=prefix, user=user, password=password, tenant=tenant)

    # Fallback global
    url = settings.PROTHEUS_URL
    if not url:
        raise HTTPException(
            status_code=422,
            detail=(
                "URL do Protheus nao configurada. "
                "Informe o parametro 'empresa_id' ou defina PROTHEUS_URL no .env"
            ),
        )

    return ProtheusConfig(
        url=url,
        rest_prefix="rest",
        user=settings.PROTHEUS_USER,
        password=settings.PROTHEUS_PASSWORD,
        tenant=settings.PROTHEUS_TENANT or "",
    )


def resolve_protheus_tenant(empresa_id: Optional[int], db: Optional[Session]) -> str:
    """Mantido para compatibilidade. Prefira resolve_protheus_config."""
    return resolve_protheus_config(empresa_id, db).tenant
