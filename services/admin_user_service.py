from typing import List, Optional
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.security import hash_password, validate_password_strength
from models import Usuario, UsuarioEmpresa, Empresa, Perfil, AuditLog, AuditAction


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _log_audit(db: Session, usuario_id: Optional[int], empresa_id: Optional[int], action: str, entity_type: str, entity_id: int):
    db.add(
        AuditLog(
            usuario_id=usuario_id,
            empresa_id=empresa_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    )


def listar_usuarios(db: Session) -> List[dict]:
    usuarios = db.query(Usuario).all()
    resultados = []
    for user in usuarios:
        empresas_count = (
            db.query(UsuarioEmpresa)
            .filter(UsuarioEmpresa.usuario_id == user.id, UsuarioEmpresa.is_active == True)
            .count()
        )
        resultados.append(
            {
                "id": user.id,
                "email": user.email,
                "nome": user.nome,
                "is_admin": user.is_admin,
                "is_active": user.is_active,
                "empresas_count": empresas_count,
                "last_login": user.last_login,
            }
        )
    return resultados


def obter_usuario(db: Session, usuario_id: int) -> dict:
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    associacoes = (
        db.query(UsuarioEmpresa)
        .join(Empresa, UsuarioEmpresa.empresa_id == Empresa.id)
        .join(Perfil, UsuarioEmpresa.perfil_id == Perfil.id)
        .filter(UsuarioEmpresa.usuario_id == user.id)
        .all()
    )

    empresas = []
    for assoc in associacoes:
        empresas.append(
            {
                "id": assoc.id,
                "empresa_id": assoc.empresa_id,
                "empresa_nome": assoc.empresa.nome if assoc.empresa else "",
                "empresa_cnpj": assoc.empresa.cnpj if assoc.empresa else "",
                "perfil_id": assoc.perfil_id,
                "perfil_nome": assoc.perfil.nome if assoc.perfil else "",
                "is_active": assoc.is_active,
                "created_at": assoc.created_at,
            }
        )

    return {
        "id": user.id,
        "email": user.email,
        "nome": user.nome,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
        "empresas": empresas,
    }


def criar_usuario(db: Session, data: dict) -> dict:
    email = data.get("email")
    nome = data.get("nome")
    password = data.get("password")
    is_admin = bool(data.get("is_admin", False))

    if db.query(Usuario).filter(Usuario.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ja cadastrado")

    valid, msg = validate_password_strength(password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=msg)

    user = Usuario(
        email=email,
        nome=nome,
        senha_hash=hash_password(password),
        is_admin=is_admin,
        is_active=True,
        email_verified=False,
    )
    db.add(user)
    db.flush()
    _log_audit(db, None, None, AuditAction.CREATE, "usuario", user.id)
    db.commit()

    return {
        "id": user.id,
        "email": user.email,
        "nome": user.nome,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
    }


def atualizar_usuario(db: Session, usuario_id: int, data: dict) -> dict:
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    for field in ["email", "nome", "is_admin", "is_active"]:
        if field in data and data[field] is not None:
            setattr(user, field, data[field])

    user.updated_at = _now_utc()
    _log_audit(db, None, None, AuditAction.UPDATE, "usuario", user.id)
    db.commit()

    return {
        "id": user.id,
        "email": user.email,
        "nome": user.nome,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "email_verified": user.email_verified,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login,
    }


def desativar_usuario(db: Session, usuario_id: int) -> dict:
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    user.is_active = False
    user.updated_at = _now_utc()
    _log_audit(db, None, None, AuditAction.USER_DEACTIVATE, "usuario", user.id)
    db.commit()
    return {"message": "Usuario desativado"}


def adicionar_usuario_empresa(db: Session, usuario_id: int, empresa_id: int, perfil_id: int) -> dict:
    user = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada")

    perfil = db.query(Perfil).filter(Perfil.id == perfil_id).first()
    if not perfil:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil nao encontrado")

    existentes = (
        db.query(UsuarioEmpresa)
        .filter(UsuarioEmpresa.usuario_id == usuario_id, UsuarioEmpresa.empresa_id == empresa_id)
        .all()
    )
    if existentes:
        if any(e.is_active for e in existentes):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuario ja vinculado a esta empresa",
            )
        assoc = existentes[0]
        assoc.perfil_id = perfil_id
        assoc.is_active = True
        for extra in existentes[1:]:
            db.delete(extra)
        db.commit()
        _log_audit(db, usuario_id, empresa_id, AuditAction.PERMISSION_GRANT, "usuario_empresa", assoc.id)
        return {"message": "Usuario reativado na empresa"}

    assoc = UsuarioEmpresa(
        usuario_id=usuario_id,
        empresa_id=empresa_id,
        perfil_id=perfil_id,
        is_active=True,
    )
    db.add(assoc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Usuario ja vinculado a esta empresa",
        )
    _log_audit(db, usuario_id, empresa_id, AuditAction.PERMISSION_GRANT, "usuario_empresa", assoc.id)
    return {"message": "Usuario adicionado a empresa"}


def remover_usuario_empresa(db: Session, usuario_id: int, empresa_id: int) -> dict:
    assoc = (
        db.query(UsuarioEmpresa)
        .filter(UsuarioEmpresa.usuario_id == usuario_id, UsuarioEmpresa.empresa_id == empresa_id)
        .first()
    )
    if not assoc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associacao nao encontrada")

    db.delete(assoc)
    db.commit()
    _log_audit(db, usuario_id, empresa_id, AuditAction.PERMISSION_REVOKE, "usuario_empresa", assoc.id)
    return {"message": "Usuario removido da empresa"}
