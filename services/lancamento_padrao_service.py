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
        .order_by(LancamentoPadrao.lp_codigo)
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
    Insere novos LPs sem sobrescrever configurações existentes (cfops/colunas_sft).
    Retorna quantidade de novos registros criados.
    """
    lps_vistos: dict[str, str] = {}
    for r in registros:
        lp = str(r.get("ct2_lp") or "").strip()
        desc = str(r.get("ct5_desc") or "").strip()
        if lp and lp not in lps_vistos:
            lps_vistos[lp] = desc

    existentes = {
        row.lp_codigo: row
        for row in db.query(LancamentoPadrao).filter(LancamentoPadrao.empresa_id == empresa_id).all()
    }

    novos = 0
    for lp_codigo, descricao in lps_vistos.items():
        if lp_codigo in existentes:
            ex = existentes[lp_codigo]
            if descricao and not ex.descricao:
                ex.descricao = descricao
        else:
            db.add(LancamentoPadrao(
                empresa_id=empresa_id,
                lp_codigo=lp_codigo,
                descricao=descricao or None,
            ))
            novos += 1

    db.commit()
    logger.info("upsert_de_carga empresa=%s: %s LPs novos de %s total", empresa_id, novos, len(lps_vistos))
    return novos
