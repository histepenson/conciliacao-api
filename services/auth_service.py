from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings
from core.security import (
    verify_password,
    hash_password,
    hash_token,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_token,
    verify_reset_token,
)
from models import Usuario, UsuarioEmpresa, Empresa, Perfil, PasswordReset, UserSession, AuditLog, AuditAction
from services.empresa_configuracao_service import listar_configuracoes


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_particularidades_ativas(db: Session, empresa_id: Optional[int]) -> List[str]:
    if not empresa_id:
        return []
    return [c.chave for c in listar_configuracoes(db, empresa_id) if c.valor]


def _log_audit(
    db: Session,
    usuario_id: Optional[int],
    empresa_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
) -> None:
    log = AuditLog(
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(log)


def _empresa_info(associacao: UsuarioEmpresa) -> Dict[str, Any]:
    empresa = associacao.empresa
    perfil = associacao.perfil
    return {
        "id": empresa.id,
        "nome": empresa.nome,
        "cnpj": empresa.cnpj,
        "status": empresa.status,
        "perfil": perfil.nome if perfil else None,
    }


def _user_info(user: Usuario) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "nome": user.nome,
        "is_admin": bool(user.is_admin),
    }


def _get_user_empresas(db: Session, user_id: int, is_admin: bool = False) -> List[Dict[str, Any]]:
    if is_admin:
        empresas = db.query(Empresa).filter(Empresa.status == True).order_by(Empresa.nome).all()
        return [
            {
                "id": empresa.id,
                "nome": empresa.nome,
                "cnpj": empresa.cnpj,
                "status": empresa.status,
                "perfil": "Admin Master",
            }
            for empresa in empresas
        ]

    associacoes = (
        db.query(UsuarioEmpresa)
        .join(Empresa, UsuarioEmpresa.empresa_id == Empresa.id)
        .join(Perfil, UsuarioEmpresa.perfil_id == Perfil.id)
        .filter(UsuarioEmpresa.usuario_id == user_id, UsuarioEmpresa.is_active == True)
        .all()
    )
    return [_empresa_info(a) for a in associacoes]


def _get_user_permissions_for_empresa(
    db: Session, user: Usuario, empresa_id: Optional[int]
) -> List[str]:
    if user.is_admin and not empresa_id:
        return ["*"]
    if not empresa_id:
        return []

    assoc = (
        db.query(UsuarioEmpresa)
        .filter(
            UsuarioEmpresa.usuario_id == user.id,
            UsuarioEmpresa.empresa_id == empresa_id,
            UsuarioEmpresa.is_active == True,
        )
        .first()
    )
    if not assoc:
        return ["*"] if user.is_admin else []
    perfil = db.query(Perfil).filter(Perfil.id == assoc.perfil_id).first()
    return perfil.permissoes if perfil else []


def login(
    db: Session,
    email: str,
    password: str,
) -> Dict[str, Any]:
    email_normalizado = (email or "").strip().lower()
    user = db.query(Usuario).filter(func.lower(Usuario.email) == email_normalizado).first()
    if not user or not user.is_active:
        _log_audit(db, None, None, AuditAction.LOGIN_FAILED, "usuario", None)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais invalidas",
        )

    if not verify_password(password, user.senha_hash):
        _log_audit(db, user.id, None, AuditAction.LOGIN_FAILED, "usuario", user.id)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais invalidas",
        )

    access_token = create_access_token(user_id=user.id, empresa_id=None, is_admin=user.is_admin)
    refresh_token = create_refresh_token(user_id=user.id)

    user.last_login = _now_utc()
    _log_audit(db, user.id, None, AuditAction.LOGIN, "usuario", user.id)

    # Registrar sessao (refresh token)
    expires_at = _now_utc() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    session = UserSession(
        usuario_id=user.id,
        token_hash=hash_token(refresh_token),
        empresa_id=None,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()

    empresas = _get_user_empresas(db, user.id, user.is_admin)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": _user_info(user),
        "empresas": empresas,
    }


def refresh_access_token(db: Session, refresh_token: str) -> Dict[str, Any]:
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")

    user = db.query(Usuario).filter(Usuario.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario invalido")

    # Validar sessao
    valid_session = (
        db.query(UserSession)
        .filter(
            UserSession.usuario_id == user.id,
            UserSession.token_hash == hash_token(refresh_token),
            UserSession.revoked_at.is_(None),
        )
        .first()
    )

    if valid_session is None or valid_session.is_expired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")

    access_token = create_access_token(user_id=user.id, empresa_id=None, is_admin=user.is_admin)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def logout(db: Session, refresh_token: Optional[str]) -> Dict[str, Any]:
    if not refresh_token:
        return {"message": "Logout realizado"}

    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        return {"message": "Logout realizado"}

    user_id = payload.get("sub")
    if not user_id:
        return {"message": "Logout realizado"}

    sess = (
        db.query(UserSession)
        .filter(
            UserSession.usuario_id == int(user_id),
            UserSession.token_hash == hash_token(refresh_token),
            UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if sess:
        sess.revoked_at = _now_utc()
        _log_audit(db, int(user_id), None, AuditAction.LOGOUT, "usuario", int(user_id))
        db.commit()

    return {"message": "Logout realizado"}


def select_empresa(
    db: Session,
    user: Usuario,
    empresa_id: int,
) -> Dict[str, Any]:
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa or not empresa.status:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada")

    if not user.is_admin:
        assoc = (
            db.query(UsuarioEmpresa)
            .filter(
                UsuarioEmpresa.usuario_id == user.id,
                UsuarioEmpresa.empresa_id == empresa_id,
                UsuarioEmpresa.is_active == True,
            )
            .first()
        )
        if not assoc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a empresa")
    else:
        assoc = (
            db.query(UsuarioEmpresa)
            .filter(
                UsuarioEmpresa.usuario_id == user.id,
                UsuarioEmpresa.empresa_id == empresa_id,
                UsuarioEmpresa.is_active == True,
            )
            .first()
        )

    permissoes = _get_user_permissions_for_empresa(db, user, empresa_id)
    particularidades = _get_particularidades_ativas(db, empresa_id)
    access_token = create_access_token(user_id=user.id, empresa_id=empresa_id, is_admin=user.is_admin)

    _log_audit(db, user.id, empresa_id, AuditAction.EMPRESA_SELECT, "empresa", empresa_id)
    db.commit()

    perfil_nome = assoc.perfil.nome if assoc and assoc.perfil else None
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "empresa": {
            "id": empresa.id,
            "nome": empresa.nome,
            "cnpj": empresa.cnpj,
            "status": empresa.status,
            "perfil": perfil_nome,
        },
        "permissoes": permissoes,
        "particularidades": particularidades,
    }


def me(db: Session, user: Usuario, empresa_id: Optional[int]) -> Dict[str, Any]:
    empresas = _get_user_empresas(db, user.id, user.is_admin)
    empresa_atual = None
    if empresa_id:
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if empresa:
            empresa_atual = {
                "id": empresa.id,
                "nome": empresa.nome,
                "cnpj": empresa.cnpj,
                "status": empresa.status,
                "perfil": None,
            }
    permissoes = _get_user_permissions_for_empresa(db, user, empresa_id)
    particularidades = _get_particularidades_ativas(db, empresa_id)
    return {
        "id": user.id,
        "email": user.email,
        "nome": user.nome,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "empresa_atual": empresa_atual,
        "permissoes": permissoes,
        "particularidades": particularidades,
        "empresas": empresas,
    }


def request_password_reset(db: Session, email: str) -> Dict[str, Any]:
    email_normalizado = (email or "").strip().lower()
    user = db.query(Usuario).filter(func.lower(Usuario.email) == email_normalizado).first()
    if not user:
        return {"message": "Se o email existir, voce recebera instrucoes para redefinir sua senha."}

    token_plain, token_hash = generate_reset_token()
    expires_at = _now_utc() + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)

    reset = PasswordReset(
        usuario_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset)
    _log_audit(db, user.id, None, AuditAction.PASSWORD_RESET_REQUEST, "usuario", user.id)
    db.commit()

    # TODO: integrar envio de email (SMTP)
    _ = token_plain
    return {"message": "Se o email existir, voce recebera instrucoes para redefinir sua senha."}


def reset_password(db: Session, token: str, new_password: str) -> Dict[str, Any]:
    valid, msg = validate_password_strength(new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

    resets = (
        db.query(PasswordReset)
        .filter(PasswordReset.used_at.is_(None))
        .order_by(PasswordReset.created_at.desc())
        .all()
    )
    reset = None
    for r in resets:
        if r.is_valid and verify_reset_token(token, r.token_hash):
            reset = r
            break

    if not reset:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token invalido ou expirado")

    user = db.query(Usuario).filter(Usuario.id == reset.usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario invalido")

    user.senha_hash = hash_password(new_password)
    reset.used_at = _now_utc()
    _log_audit(db, user.id, None, AuditAction.PASSWORD_RESET, "usuario", user.id)
    db.commit()

    return {"message": "Senha redefinida com sucesso."}
