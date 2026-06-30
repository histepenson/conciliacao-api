import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.lancamento_padrao import LancamentoPadrao

logger = logging.getLogger(__name__)


def _sequencia_do_origem(origem) -> str:
    """
    Fallback para extrair a sequencia quando ct2_sequen vem vazio - acontece em
    cargas CT2RAZCT5 carregadas antes do campo ct2_sequen existir no
    ZCT2RAZCT5.prw (ou em ambientes cujo .prw ainda nao foi atualizado).
    ct2_origem guarda "LP-SEQUENCIA" nos primeiros 7 caracteres, mesma logica
    do JOIN feito no .prw: SUBSTRING(CT2.CT2_ORIGEM,1,7).
    """
    partes = str(origem or "").strip()[:7].split("-")
    return partes[1].strip() if len(partes) == 2 else ""


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
    campos = (
        "descricao",
        "sequencia",
        "grupo",
        "cfops",
        "tes_codes",
        "cfops_excluir",
        "tes_codes_excluir",
        "series",
        "especies",
        "especies_excluir",
        "colunas_sft",
        "colunas_valor_sft",
        "ativo",
    )
    for campo in campos:
        if campo in dados:
            setattr(lp, campo, dados[campo])
    db.commit()
    db.refresh(lp)
    return lp


def bulk_definir_grupo(db: Session, empresa_id: int, ids: list[int], grupo: str | None) -> int:
    """Define (ou remove) o grupo de múltiplos LPs de uma vez."""
    atualizados = (
        db.query(LancamentoPadrao)
        .filter(LancamentoPadrao.empresa_id == empresa_id, LancamentoPadrao.id.in_(ids))
        .all()
    )
    for lp in atualizados:
        lp.grupo = grupo or None
    db.commit()
    return len(atualizados)


def upsert_de_carga(db: Session, empresa_id: int, registros: list[dict]) -> int:
    """
    Chamado após carga CT2RAZCT5 concluída.
    Agrupa por (ct2_lp, ct5_desc) — um LP pode ter múltiplas descrições (sequências 001, 002...).
    Insere novos pares sem sobrescrever configurações existentes (cfops/colunas_sft) e faz
    backfill da sequencia em LPs já cadastrados que ainda não tinham esse campo (sem tocar
    em nenhuma outra configuração já feita pelo usuário).
    Retorna quantidade de novos registros criados.
    """
    sequencia_por_par: dict[tuple[str, str], str] = {}
    for r in registros:
        lp = str(r.get("ct2_lp") or "").strip()
        desc = str(r.get("ct5_desc") or "").strip()
        sequencia = str(r.get("ct2_sequen") or "").strip() or _sequencia_do_origem(r.get("ct2_origem"))
        if lp and (lp, desc) not in sequencia_por_par:
            sequencia_por_par[(lp, desc)] = sequencia

    existentes: dict[tuple[str, str], LancamentoPadrao] = {
        (row.lp_codigo, row.descricao or ""): row
        for row in db.query(LancamentoPadrao).filter(LancamentoPadrao.empresa_id == empresa_id).all()
    }

    novos = 0
    for (lp_codigo, descricao), sequencia in sorted(sequencia_por_par.items()):
        existente = existentes.get((lp_codigo, descricao))
        if existente is None:
            db.add(LancamentoPadrao(
                empresa_id=empresa_id,
                lp_codigo=lp_codigo,
                descricao=descricao,
                sequencia=sequencia or None,
            ))
            novos += 1
        elif not existente.sequencia and sequencia:
            existente.sequencia = sequencia

    db.commit()
    logger.info("upsert_de_carga empresa=%s: %s novos de %s pares únicos", empresa_id, novos, len(sequencia_por_par))
    return novos
