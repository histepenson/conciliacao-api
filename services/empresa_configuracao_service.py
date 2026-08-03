from typing import Any, List, Optional
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.particularidades import ChaveParticularidade
from models import EmpresaConfiguracao, AuditLog, AuditAction

_ENTITY_TYPE = "empresa_configuracao"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _log_audit(db: Session, usuario_id: Optional[int], empresa_id: Optional[int], action: str, entity_id: int):
    db.add(
        AuditLog(
            usuario_id=usuario_id,
            empresa_id=empresa_id,
            action=action,
            entity_type=_ENTITY_TYPE,
            entity_id=entity_id,
        )
    )


def _validar_chave(chave: str) -> None:
    if chave not in {c.value for c in ChaveParticularidade}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chave de particularidade desconhecida: '{chave}'",
        )


def listar_configuracoes(db: Session, empresa_id: int) -> List[EmpresaConfiguracao]:
    return (
        db.query(EmpresaConfiguracao)
        .filter(EmpresaConfiguracao.empresa_id == empresa_id)
        .order_by(EmpresaConfiguracao.chave)
        .all()
    )


def obter_valor(db: Session, empresa_id: Optional[int], chave: str) -> Optional[Any]:
    if not empresa_id:
        return None
    config = (
        db.query(EmpresaConfiguracao)
        .filter(
            EmpresaConfiguracao.empresa_id == empresa_id,
            EmpresaConfiguracao.chave == chave,
        )
        .first()
    )
    return config.valor if config else None


def definir_configuracao(
    db: Session,
    empresa_id: int,
    chave: str,
    valor: Any,
    usuario_id: Optional[int] = None,
) -> EmpresaConfiguracao:
    _validar_chave(chave)

    config = (
        db.query(EmpresaConfiguracao)
        .filter(
            EmpresaConfiguracao.empresa_id == empresa_id,
            EmpresaConfiguracao.chave == chave,
        )
        .first()
    )

    if config:
        config.valor = valor
        config.atualizado_por = usuario_id
        config.atualizado_em = _now_utc()
    else:
        config = EmpresaConfiguracao(
            empresa_id=empresa_id,
            chave=chave,
            valor=valor,
            criado_por=usuario_id,
            atualizado_por=usuario_id,
        )
        db.add(config)

    db.flush()
    _log_audit(db, usuario_id, empresa_id, AuditAction.UPDATE, config.id)
    db.commit()
    return config


def remover_configuracao(db: Session, empresa_id: int, chave: str, usuario_id: Optional[int] = None) -> dict:
    _validar_chave(chave)

    config = (
        db.query(EmpresaConfiguracao)
        .filter(
            EmpresaConfiguracao.empresa_id == empresa_id,
            EmpresaConfiguracao.chave == chave,
        )
        .first()
    )
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuracao nao encontrada")

    config_id = config.id
    db.delete(config)
    _log_audit(db, usuario_id, empresa_id, AuditAction.DELETE, config_id)
    db.commit()
    return {"message": "Configuracao removida"}
