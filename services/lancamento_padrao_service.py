import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.lancamento_padrao import LancamentoPadrao

logger = logging.getLogger(__name__)


def listar(db: Session, empresa_id: int) -> list[LancamentoPadrao]:
    return (
        db.query(LancamentoPadrao)
        .filter(LancamentoPadrao.empresa_id == empresa_id)
        .order_by(LancamentoPadrao.lp_codigo, LancamentoPadrao.descricao)
        .all()
    )


def obter(db: Session, lp_id: int, empresa_id: int) -> LancamentoPadrao:
    lp = db.query(LancamentoPadrao).filter(
        LancamentoPadrao.id == lp_id,
        LancamentoPadrao.empresa_id == empresa_id,
    ).first()
    if not lp:
        raise HTTPException(404, "Lancamento padrao nao encontrado")
    return lp


def atualizar(db: Session, lp_id: int, empresa_id: int, dados: dict) -> LancamentoPadrao:
    lp = obter(db, lp_id, empresa_id)
    campos = ("descricao", "cfops", "colunas_sft", "ativo")
    for campo in campos:
        if campo in dados:
            setattr(lp, campo, dados[campo])
    db.commit()
    db.refresh(lp)
    return lp


def upsert_de_carga(db: Session, empresa_id: int, registros: list[dict]) -> int:
    """
    Chamado após carga CT2RAZCT5 concluída.
    Agrupa por (ct2_lp, ct5_desc) — um LP pode ter múltiplas descrições (sequências 001, 002...).
    Insere novos pares sem sobrescrever configurações existentes (cfops/colunas_sft).
    Retorna quantidade de novos registros criados.
    """
    pares_vistos: set[tuple[str, str]] = set()
    for r in registros:
        lp = str(r.get("ct2_lp") or "").strip()
        desc = str(r.get("ct5_desc") or "").strip()
        if lp:
            pares_vistos.add((lp, desc))

    existentes: set[tuple[str, str]] = {
        (row.lp_codigo, row.descricao or "")
        for row in db.query(LancamentoPadrao).filter(LancamentoPadrao.empresa_id == empresa_id).all()
    }

    novos = 0
    for lp_codigo, descricao in sorted(pares_vistos):
        if (lp_codigo, descricao) not in existentes:
            db.add(LancamentoPadrao(
                empresa_id=empresa_id,
                lp_codigo=lp_codigo,
                descricao=descricao,
            ))
            novos += 1

    db.commit()
    logger.info("upsert_de_carga empresa=%s: %s novos de %s pares únicos", empresa_id, novos, len(pares_vistos))
    return novos
