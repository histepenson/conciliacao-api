from typing import List, Optional
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Empresa, UsuarioEmpresa, Usuario, Perfil, AuditLog, AuditAction


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

def listar_empresas(db: Session) -> List[dict]:
    counts = {
        row.empresa_id: row.total
        for row in db.query(
            UsuarioEmpresa.empresa_id,
            func.count(UsuarioEmpresa.usuario_id).label("total")
        ).group_by(UsuarioEmpresa.empresa_id).all()
    }
    empresas = db.query(Empresa).all()
    result = []
    for e in empresas:
        d = {c.name: getattr(e, c.name) for c in e.__table__.columns}
        d["usuarios_count"] = counts.get(e.id, 0)
        result.append(d)
    return result


def obter_empresa(db: Session, empresa_id: int) -> Empresa:
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empresa nao encontrada")
    return empresa


def criar_empresa(db: Session, data: dict, created_by: Optional[int] = None) -> Empresa:
    if db.query(Empresa).filter(Empresa.cnpj == data.get("cnpj")).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="CNPJ ja cadastrado")

    empresa = Empresa(
        nome=data.get("nome"),
        cnpj=data.get("cnpj"),
        status=bool(data.get("status", True)),
        created_by=created_by,
    )
    db.add(empresa)
    db.flush()
    _log_audit(db, created_by, empresa.id, AuditAction.CREATE, "empresa", empresa.id)
    db.commit()
    return empresa


def atualizar_empresa(db: Session, empresa_id: int, data: dict, updated_by: Optional[int] = None) -> Empresa:
    empresa = obter_empresa(db, empresa_id)
    for field in ["nome", "cnpj", "status", "permite_efetivar_divergente", "protheus_tenant"]:
        if field in data and data[field] is not None:
            setattr(empresa, field, data[field])
    empresa.updated_by = updated_by
    empresa.updated_at = _now_utc()
    _log_audit(db, updated_by, empresa.id, AuditAction.UPDATE, "empresa", empresa.id)
    db.commit()
    return empresa


def desativar_empresa(db: Session, empresa_id: int, updated_by: Optional[int] = None) -> dict:
    empresa = obter_empresa(db, empresa_id)
    empresa.status = False
    empresa.updated_by = updated_by
    empresa.updated_at = _now_utc()
    _log_audit(db, updated_by, empresa.id, AuditAction.DELETE, "empresa", empresa.id)
    db.commit()
    return {"message": "Empresa desativada"}


def listar_usuarios_da_empresa(db: Session, empresa_id: int) -> List[dict]:
    assoc = (
        db.query(
            UsuarioEmpresa,
            Usuario.nome,
            Usuario.email,
            Empresa.nome,
            Empresa.cnpj,
            Perfil.nome,
        )
        .outerjoin(Usuario, UsuarioEmpresa.usuario_id == Usuario.id)
        .outerjoin(Empresa, UsuarioEmpresa.empresa_id == Empresa.id)
        .outerjoin(Perfil, UsuarioEmpresa.perfil_id == Perfil.id)
        .filter(UsuarioEmpresa.empresa_id == empresa_id)
        .all()
    )
    resultados = []
    for a, usuario_nome, usuario_email, empresa_nome, empresa_cnpj, perfil_nome in assoc:
        resultados.append(
            {
                "id": a.id,
                "usuario_id": a.usuario_id,
                "usuario_nome": usuario_nome or "",
                "usuario_email": usuario_email or "",
                "empresa_id": a.empresa_id,
                "empresa_nome": empresa_nome or "",
                "empresa_cnpj": empresa_cnpj or "",
                "perfil_id": a.perfil_id,
                "perfil_nome": perfil_nome or "",
                "is_active": a.is_active,
                "created_at": a.created_at,
            }
        )
    return resultados
