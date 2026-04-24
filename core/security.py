# core/security.py
from datetime import datetime, timedelta
from typing import Optional
import secrets
import re

from jose import jwt, JWTError
from passlib.context import CryptContext

from .config import settings

# Contexto de hash para senhas (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Gera hash da senha usando bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha corresponde ao hash."""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Valida a forca da senha conforme politica definida.
    Retorna (valido, mensagem_erro).
    """
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"Senha deve ter no minimo {settings.PASSWORD_MIN_LENGTH} caracteres"

    if settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        return False, "Senha deve conter pelo menos uma letra maiuscula"

    if settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        return False, "Senha deve conter pelo menos uma letra minuscula"

    if settings.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        return False, "Senha deve conter pelo menos um numero"

    if settings.PASSWORD_REQUIRE_SPECIAL:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?/"
        if not any(c in special_chars for c in password):
            return False, "Senha deve conter pelo menos um caractere especial"

    return True, ""


def create_access_token(
    user_id: int,
    empresa_id: Optional[int] = None,
    is_admin: bool = False,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Cria token JWT de acesso.

    Args:
        user_id: ID do usuario
        empresa_id: ID da empresa selecionada (opcional)
        is_admin: Se o usuario e admin master
        expires_delta: Tempo de expiracao customizado

    Returns:
        Token JWT codificado
    """
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": str(user_id),
        "empresa_id": empresa_id,
        "is_admin": is_admin,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access",
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """
    Cria refresh token JWT (validade maior).

    Args:
        user_id: ID do usuario

    Returns:
        Refresh token JWT codificado
    """
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",
    }

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    Decodifica e valida um token JWT.

    Args:
        token: Token JWT

    Returns:
        Payload do token ou None se invalido
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


def generate_reset_token() -> tuple[str, str]:
    """
    Gera token de reset de senha e seu hash.

    Returns:
        Tupla (token_plain, token_hash)
        - token_plain: Enviado por email
        - token_hash: Armazenado no banco
    """
    token = secrets.token_urlsafe(32)
    token_hash = pwd_context.hash(token)
    return token, token_hash


def verify_reset_token(plain_token: str, hashed_token: str) -> bool:
    """
    Verifica se o token de reset corresponde ao hash.

    Args:
        plain_token: Token recebido do usuario
        hashed_token: Hash armazenado no banco

    Returns:
        True se valido
    """
    return pwd_context.verify(plain_token, hashed_token)


def generate_session_id() -> str:
    """Gera ID unico para sessao."""
    return secrets.token_urlsafe(32)
