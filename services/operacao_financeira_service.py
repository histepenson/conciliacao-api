# services/operacao_financeira_service.py
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.operacao_financeira import OperacaoFinanceira


def listar_operacoes_financeiras(
    db: Session,
    empresa_id: int,
    skip: int = 0,
    limit: int = 1000,
    modalidade: Optional[str] = None,
    ativo: Optional[bool] = None,
) -> List[OperacaoFinanceira]:
    query = db.query(OperacaoFinanceira).filter(OperacaoFinanceira.empresa_id == empresa_id)
    if modalidade:
        query = query.filter(OperacaoFinanceira.modalidade == modalidade.strip().upper())
    if ativo is not None:
        query = query.filter(OperacaoFinanceira.ativo == ativo)
    return query.order_by(OperacaoFinanceira.codigo).offset(skip).limit(limit).all()


def buscar_operacao_financeira(db: Session, id: int, empresa_id: Optional[int] = None) -> Optional[OperacaoFinanceira]:
    query = db.query(OperacaoFinanceira).filter(OperacaoFinanceira.id == id)
    if empresa_id is not None:
        query = query.filter(OperacaoFinanceira.empresa_id == empresa_id)
    return query.first()


def criar_operacao_financeira(db: Session, dados: dict) -> OperacaoFinanceira:
    # Regra: modalidade so' existe pra natureza ativa. Inativa nasce sem
    # modalidade, mesmo que uma tenha sido enviada no formulario.
    if dados.get("ativo", True) is False:
        dados["modalidade"] = None

    db_operacao = OperacaoFinanceira(**dados)
    db.add(db_operacao)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Codigo '{dados.get('codigo')}' ja cadastrado para esta empresa")
    db.refresh(db_operacao)
    return db_operacao


def atualizar_operacao_financeira(db: Session, id: int, dados: dict, empresa_id: Optional[int] = None) -> Optional[OperacaoFinanceira]:
    db_operacao = buscar_operacao_financeira(db, id, empresa_id)
    if not db_operacao:
        return None
    for key, value in dados.items():
        setattr(db_operacao, key, value)

    # Regra: modalidade so' existe pra natureza ativa. Reavalia com o
    # `ativo` final (recem-atualizado ou o que ja estava salvo) -- se
    # inativa, zera a modalidade mesmo que nao tenha vindo no payload.
    if not db_operacao.ativo:
        db_operacao.modalidade = None

    db_operacao.updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Codigo '{dados.get('codigo')}' ja cadastrado para esta empresa")
    db.refresh(db_operacao)
    return db_operacao


def deletar_operacao_financeira(db: Session, id: int, empresa_id: Optional[int] = None) -> bool:
    db_operacao = buscar_operacao_financeira(db, id, empresa_id)
    if not db_operacao:
        return False
    db.delete(db_operacao)
    db.commit()
    return True
