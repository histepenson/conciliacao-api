from typing import List, Optional
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from middleware.permission import ALL_PERMISSIONS
from models import Perfil, AuditLog, AuditAction


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _log_audit(db: Session, usuario_id: Optional[int], action: str, entity_id: int):
    db.add(
        AuditLog(
            usuario_id=usuario_id,
            empresa_id=None,
            action=action,
            entity_type="perfil",
            entity_id=entity_id,
        )
    )


def _validar_permissoes(permissoes: List[str]) -> None:
    invalid = [p for p in permissoes if p not in ALL_PERMISSIONS and p != "*"]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Permissoes invalidas: {', '.join(invalid)}",
        )


def listar_perfis(db: Session) -> List[Perfil]:
    return db.query(Perfil).all()


def obter_perfil(db: Session, perfil_id: int) -> Perfil:
    perfil = db.query(Perfil).filter(Perfil.id == perfil_id).first()
    if not perfil:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil nao encontrado")
    return perfil


def criar_perfil(db: Session, data: dict, created_by: Optional[int] = None) -> Perfil:
    if db.query(Perfil).filter(Perfil.nome == data.get("nome")).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Perfil ja existe")

    permissoes = data.get("permissoes", [])
    _validar_permissoes(permissoes)

    perfil = Perfil(
        nome=data.get("nome"),
        descricao=data.get("descricao"),
        permissoes=permissoes,
        is_system=False,
    )
    db.add(perfil)
    db.flush()
    _log_audit(db, created_by, AuditAction.CREATE, perfil.id)
    db.commit()
    return perfil


def atualizar_perfil(db: Session, perfil_id: int, data: dict, updated_by: Optional[int] = None) -> Perfil:
    perfil = obter_perfil(db, perfil_id)
    if perfil.is_system:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil do sistema nao pode ser alterado")

    if "nome" in data and data["nome"] is not None:
        perfil.nome = data["nome"]
    if "descricao" in data:
        perfil.descricao = data["descricao"]
    if "permissoes" in data and data["permissoes"] is not None:
        _validar_permissoes(data["permissoes"])
        perfil.permissoes = data["permissoes"]

    perfil.updated_at = _now_utc()
    _log_audit(db, updated_by, AuditAction.UPDATE, perfil.id)
    db.commit()
    return perfil


def deletar_perfil(db: Session, perfil_id: int, deleted_by: Optional[int] = None) -> dict:
    perfil = obter_perfil(db, perfil_id)
    if perfil.is_system:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil do sistema nao pode ser removido")

    db.delete(perfil)
    _log_audit(db, deleted_by, AuditAction.DELETE, perfil.id)
    db.commit()
    return {"message": "Perfil removido"}
