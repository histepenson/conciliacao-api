# services/leasing_regra_classificacao_service.py
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from models.leasing_regra_classificacao import LeasingRegraClassificacao


def listar_regras(db: Session, empresa_id: int, apenas_ativas: bool = False) -> List[LeasingRegraClassificacao]:
    query = db.query(LeasingRegraClassificacao).filter(LeasingRegraClassificacao.empresa_id == empresa_id)
    if apenas_ativas:
        query = query.filter(LeasingRegraClassificacao.ativo.is_(True))
    return query.order_by(LeasingRegraClassificacao.padrao_cliente).all()


def buscar_regra(db: Session, id: int, empresa_id: Optional[int] = None) -> Optional[LeasingRegraClassificacao]:
    query = db.query(LeasingRegraClassificacao).filter(LeasingRegraClassificacao.id == id)
    if empresa_id is not None:
        query = query.filter(LeasingRegraClassificacao.empresa_id == empresa_id)
    return query.first()


def criar_regra(db: Session, dados: dict) -> LeasingRegraClassificacao:
    db_regra = LeasingRegraClassificacao(**dados)
    db.add(db_regra)
    db.commit()
    db.refresh(db_regra)
    return db_regra


def atualizar_regra(db: Session, id: int, dados: dict, empresa_id: Optional[int] = None) -> Optional[LeasingRegraClassificacao]:
    db_regra = buscar_regra(db, id, empresa_id)
    if not db_regra:
        return None
    for key, value in dados.items():
        setattr(db_regra, key, value)
    db_regra.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_regra)
    return db_regra


def deletar_regra(db: Session, id: int, empresa_id: Optional[int] = None) -> bool:
    db_regra = buscar_regra(db, id, empresa_id)
    if not db_regra:
        return False
    db.delete(db_regra)
    db.commit()
    return True
