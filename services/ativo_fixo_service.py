"""
Servico de conciliacao de Ativo Fixo: confronta os movimentos de Baixa
(SN3 — credito do razao) e de Lancamento (SN4 — debito do razao) com o
razao contabil (CT2RAZCT5), filtrado pela(s) conta(s) de Ativo Fixo.

Fluxo:
  1. Busca a ultima carga concluida de SN3, SN4 e CT2RAZCT5 para a empresa.
  2. Filtra o razao pela(s) conta(s) informada(s) (conta_de/conta_ate).
  3. Monta, para cada registro SN3/SN4, a mesma chave usada pelo Protheus
     ao gravar ct2_key nas linhas do razao geradas por aquele movimento:
       SN4 (debito): N4_FILIAL + N4_CBASE + N4_ITEM + N4_TIPO + DTOS(N4_DATA) + N4_OCORR + N4_SEQ
       SN3 (credito): N3_FILIAL + N3_CBASE + N3_ITEM + N3_TIPO + N3_BAIXA + N3_SEQ
  4. Casa SN3 contra a coluna credito do razao e SN4 contra a coluna debito,
     via tools/fiscal/match_sn_razao.match_sn_razao.
"""

import logging
import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro
from tools.fiscal.match_sn_razao import match_sn_razao

logger = logging.getLogger(__name__)


def _ultima_carga(db: Session, empresa_id: int, tipo: str) -> ProtheusCarga | None:
    return (
        db.query(ProtheusCarga)
        .filter(
            ProtheusCarga.empresa_id == empresa_id,
            ProtheusCarga.tipo_relatorio == tipo,
            ProtheusCarga.status == "concluido",
        )
        .order_by(ProtheusCarga.finalizado_em.desc())
        .first()
    )


def _carregar_dados_carga(db: Session, carga_id: int) -> list[dict]:
    return [
        r.dados_json
        for r in db.query(ProtheusCargaRegistro)
        .filter(ProtheusCargaRegistro.carga_id == carga_id)
        .order_by(ProtheusCargaRegistro.sequencia)
        .all()
    ]


def _data_br_para_dtos(valor: str) -> str:
    """Converte 'DD/MM/YYYY' (formato de DtoC do ADVPL) para 'YYYYMMDD' (DTOS)."""
    v = str(valor or "").strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", v)
    if m:
        dia, mes, ano = m.groups()
        return f"{ano}{mes}{dia}"
    return re.sub(r"\D", "", v)


def _chave_sn4(rec: dict) -> str:
    filial = str(rec.get("filial") or "").strip()
    cbase = str(rec.get("cbase") or "").strip()
    item = str(rec.get("item") or "").strip()
    tipo = str(rec.get("tipo") or "").strip()
    data = _data_br_para_dtos(rec.get("data"))
    ocorr = str(rec.get("ocorr") or "").strip()
    seq = str(rec.get("seq") or "").strip()
    if not (filial and cbase and item):
        return ""
    return filial + cbase + item + tipo + data + ocorr + seq


def _chave_sn3(rec: dict) -> str:
    filial = str(rec.get("filial") or "").strip()
    cbase = str(rec.get("cbase") or "").strip()
    item = str(rec.get("item") or "").strip()
    tipo = str(rec.get("tipo") or "").strip()
    baixa = str(rec.get("baixa") or "").strip()
    seq = str(rec.get("seq") or "").strip()
    if not (filial and cbase and item):
        return ""
    return filial + cbase + item + tipo + baixa + seq


def _filtrar_razao_por_conta(razao_recs: list[dict], conta_de: Optional[str], conta_ate: Optional[str]) -> list[dict]:
    if not conta_de and not conta_ate:
        return razao_recs
    de = str(conta_de or "").strip()
    ate = str(conta_ate or "zzzzzzzzzzzzzzz").strip()
    return [r for r in razao_recs if de <= str(r.get("conta") or "").strip() <= ate]


def conferir(
    db: Session,
    empresa_id: int,
    carga_id_sn3: int | None = None,
    carga_id_sn4: int | None = None,
    carga_id_razao: int | None = None,
    conta_de: Optional[str] = None,
    conta_ate: Optional[str] = None,
) -> dict:
    # ── Resolucao das cargas ─────────────────────────────────────────────────
    if carga_id_sn3 is None:
        carga_sn3 = _ultima_carga(db, empresa_id, "SN3")
        if not carga_sn3:
            raise HTTPException(404, "Nenhuma carga SN3 concluida encontrada para esta empresa.")
        carga_id_sn3 = carga_sn3.id
    else:
        carga_sn3 = db.query(ProtheusCarga).get(carga_id_sn3)
        if not carga_sn3 or carga_sn3.empresa_id != empresa_id:
            raise HTTPException(404, f"Carga SN3 {carga_id_sn3} nao encontrada.")

    if carga_id_sn4 is None:
        carga_sn4 = _ultima_carga(db, empresa_id, "SN4")
        if not carga_sn4:
            raise HTTPException(404, "Nenhuma carga SN4 concluida encontrada para esta empresa.")
        carga_id_sn4 = carga_sn4.id
    else:
        carga_sn4 = db.query(ProtheusCarga).get(carga_id_sn4)
        if not carga_sn4 or carga_sn4.empresa_id != empresa_id:
            raise HTTPException(404, f"Carga SN4 {carga_id_sn4} nao encontrada.")

    if carga_id_razao is None:
        carga_razao = _ultima_carga(db, empresa_id, "CT2RAZCT5")
        if not carga_razao:
            raise HTTPException(404, "Nenhuma carga CT2RAZCT5 concluida encontrada para esta empresa.")
        carga_id_razao = carga_razao.id
    else:
        carga_razao = db.query(ProtheusCarga).get(carga_id_razao)
        if not carga_razao or carga_razao.empresa_id != empresa_id:
            raise HTTPException(404, f"Carga CT2RAZCT5 {carga_id_razao} nao encontrada.")

    # ── Dados das cargas ─────────────────────────────────────────────────────
    sn3_data = _carregar_dados_carga(db, carga_id_sn3)
    sn4_data = _carregar_dados_carga(db, carga_id_sn4)
    razao_data = _filtrar_razao_por_conta(_carregar_dados_carga(db, carga_id_razao), conta_de, conta_ate)

    logger.info(
        "Ativo Fixo empresa=%s: sn3=%s registros (carga %s), sn4=%s registros (carga %s), razao=%s registros (carga %s, filtrado conta %s-%s)",
        empresa_id, len(sn3_data), carga_id_sn3, len(sn4_data), carga_id_sn4, len(razao_data), carga_id_razao, conta_de, conta_ate,
    )

    # ── Matching SN3 (credito) e SN4 (debito) contra o razao ────────────────
    sn3_matched, razao_matched_credito = match_sn_razao(
        sn3_data, razao_data, _chave_sn3, campo_valor_sn="vorig1", campo_valor_razao="credito",
    )
    sn4_matched, razao_matched_debito = match_sn_razao(
        sn4_data, razao_data, _chave_sn4, campo_valor_sn="vlroc1", campo_valor_razao="debito",
    )

    total_sn3 = round(sum(float(r.get("vorig1") or 0) for r in sn3_data), 2)
    total_sn4 = round(sum(float(r.get("vlroc1") or 0) for r in sn4_data), 2)
    total_razao_credito = round(sum(float(r.get("credito") or 0) for r in razao_data), 2)
    total_razao_debito = round(sum(float(r.get("debito") or 0) for r in razao_data), 2)

    sn3_nao_casados = [r for r in sn3_matched if not r["matched"]]
    sn4_nao_casados = [r for r in sn4_matched if not r["matched"]]

    resumo = {
        "total_sn3": total_sn3,
        "total_sn4": total_sn4,
        "total_razao_credito": total_razao_credito,
        "total_razao_debito": total_razao_debito,
        "diferenca_credito": round(total_sn3 - total_razao_credito, 2),
        "diferenca_debito": round(total_sn4 - total_razao_debito, 2),
        "qt_sn3": len(sn3_data),
        "qt_sn4": len(sn4_data),
        "qt_sn3_nao_casados": len(sn3_nao_casados),
        "qt_sn4_nao_casados": len(sn4_nao_casados),
        "status": (
            "ok"
            if abs(total_sn3 - total_razao_credito) <= 0.01 and abs(total_sn4 - total_razao_debito) <= 0.01
            else "diferente"
        ),
    }

    return {
        "empresa_id": empresa_id,
        "carga_id_sn3": carga_id_sn3,
        "carga_id_sn4": carga_id_sn4,
        "carga_id_razao": carga_id_razao,
        "conta_de": conta_de,
        "conta_ate": conta_ate,
        "resumo": resumo,
        "sn3_detalhes": sn3_matched,
        "sn4_detalhes": sn4_matched,
        "razao_detalhes": razao_data,
    }
