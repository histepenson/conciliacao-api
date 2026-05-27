"""
Serviço de Pré Conferência: confronta lançamentos CT2RAZCT5 com o Livro Fiscal SFT.

Fluxo:
  1. Busca a última carga concluída de CT2RAZCT5 e SFTENT para a empresa.
  2. Carrega os registros de cada carga da tabela protheus_carga_registro.
  3. Para cada LP encontrado no CT2, usa a tabela ct5_referencia para obter a
     chave_busca (fórmula de campos que compõe o CT2_KEY).
  4. Extrai a chave parcial do CT2_KEY (apenas campos com equivalente no SFT).
  5. Constrói a mesma chave parcial para cada registro SFT.
  6. Agrupa e compara totais CT2 (débito) vs SFT (valcont) por chave.
"""

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro

logger = logging.getLogger(__name__)

# Tamanhos padrão dos campos Protheus (SX3)
TAMANHOS_CAMPO: dict[str, int] = {
    "D1_FILIAL": 2, "D1_DOC": 9, "D1_SERIE": 3,
    "D1_FORNECE": 6, "D1_LOJA": 2, "D1_TIPO": 2,
    "D1_COD": 15, "D1_ITEM": 4, "D1_SEQUEN": 4,
    "F1_FILIAL": 2, "F1_DOC": 9, "F1_SERIE": 3,
    "F1_FORNECE": 6, "F1_LOJA": 2, "F1_TIPO": 2, "F1_SEQUEN": 4,
    "E1_FILIAL": 2, "E1_CLIENTE": 6, "E1_LOJA": 2,
    "E1_PREFIXO": 3, "E1_NUM": 9, "E1_PARCELA": 2, "E1_TIPO": 3,
    "E2_FILIAL": 2, "E2_FORNECE": 6, "E2_LOJA": 2,
    "E2_PREFIXO": 3, "E2_NUM": 9, "E2_PARCELA": 2, "E2_TIPO": 3,
}

# Mapeamento campo Protheus → campo SFT (JSON key retornado pelo ZSFTENTAPI)
MAPA_CAMPO_SFT: dict[str, str] = {
    "D1_FILIAL":  "filial",
    "D1_DOC":     "nf",
    "D1_SERIE":   "serie",
    "D1_FORNECE": "fornece",
    "D1_LOJA":    "loja",
    "D1_TIPO":    "tipo",
    "F1_FILIAL":  "filial",
    "F1_DOC":     "nf",
    "F1_SERIE":   "serie",
    "F1_FORNECE": "fornece",
    "F1_LOJA":    "loja",
    "F1_TIPO":    "tipo",
}


def _parse_chave_busca(chave_busca: str) -> list[tuple[str, int]]:
    """Parseia fórmula 'D1_FILIAL+D1_DOC+...' → lista de (campo, tamanho)."""
    campos = []
    for campo in chave_busca.split("+"):
        campo = campo.strip()
        if not campo:
            continue
        tam = TAMANHOS_CAMPO.get(campo, 0)
        campos.append((campo, tam))
    return campos


def _extrair_parcial_de_ct2key(ct2_key: str, campos: list[tuple[str, int]]) -> str:
    """
    Extrai a chave parcial do CT2_KEY, usando apenas os campos que têm
    equivalente no SFT (ignorando D1_COD, D1_ITEM, etc.).
    """
    partes: list[str] = []
    pos = 0
    for campo, tam in campos:
        if tam == 0:
            continue
        segmento = ct2_key[pos: pos + tam].strip() if len(ct2_key) > pos else ""
        if campo in MAPA_CAMPO_SFT:
            partes.append(segmento)
        pos += tam
    return "|".join(partes)


def _construir_chave_sft(sft: dict[str, Any], campos: list[tuple[str, int]]) -> str:
    """
    Constrói a chave parcial para um registro SFT usando a mesma sequência
    de campos que seriam extraídos do CT2_KEY.
    """
    partes: list[str] = []
    for campo, tam in campos:
        if tam == 0:
            continue
        sft_field = MAPA_CAMPO_SFT.get(campo)
        if sft_field is None:
            continue
        val = str(sft.get(sft_field) or "").strip()
        partes.append(val)
    return "|".join(partes)


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
    registros = (
        db.query(ProtheusCargaRegistro)
        .filter(ProtheusCargaRegistro.carga_id == carga_id)
        .order_by(ProtheusCargaRegistro.sequencia)
        .all()
    )
    return [r.dados_json for r in registros]


def conferir(
    db: Session,
    empresa_id: int,
    carga_id_ct2: int | None = None,
    carga_id_sft: int | None = None,
) -> dict:
    # ── Resolução das cargas ─────────────────────────────────────────────────
    if carga_id_ct2 is None:
        carga_ct2 = _ultima_carga(db, empresa_id, "CT2RAZCT5")
        if not carga_ct2:
            raise HTTPException(404, "Nenhuma carga CT2RAZCT5 concluida encontrada para esta empresa.")
        carga_id_ct2 = carga_ct2.id
    else:
        carga_ct2 = db.query(ProtheusCarga).get(carga_id_ct2)
        if not carga_ct2 or carga_ct2.empresa_id != empresa_id:
            raise HTTPException(404, f"Carga CT2RAZCT5 {carga_id_ct2} nao encontrada.")

    if carga_id_sft is None:
        carga_sft = _ultima_carga(db, empresa_id, "SFTENT")
        if not carga_sft:
            raise HTTPException(404, "Nenhuma carga SFTENT concluida encontrada para esta empresa.")
        carga_id_sft = carga_sft.id
    else:
        carga_sft = db.query(ProtheusCarga).get(carga_id_sft)
        if not carga_sft or carga_sft.empresa_id != empresa_id:
            raise HTTPException(404, f"Carga SFTENT {carga_id_sft} nao encontrada.")

    # ── Referências CT5 ──────────────────────────────────────────────────────
    ref_rows = db.execute(
        text(
            "SELECT lp_codigo, chave_busca, descricao, alias_arq "
            "FROM concilia.ct5_referencia WHERE empresa_id = :eid"
        ),
        {"eid": empresa_id},
    ).fetchall()
    ct5_ref: dict[str, Any] = {r.lp_codigo: r for r in ref_rows}

    # ── Dados das cargas ─────────────────────────────────────────────────────
    ct2_data = _carregar_dados_carga(db, carga_id_ct2)
    sft_data = _carregar_dados_carga(db, carga_id_sft)

    logger.info(
        "Pre-conferencia empresa=%s: ct2=%s registros (carga %s), sft=%s registros (carga %s)",
        empresa_id, len(ct2_data), carga_id_ct2, len(sft_data), carga_id_sft,
    )

    # ── Agrupar CT2 por LP ───────────────────────────────────────────────────
    ct2_por_lp: dict[str, list[dict]] = {}
    for rec in ct2_data:
        lp = str(rec.get("ct2_lp") or "").strip()
        ct2_por_lp.setdefault(lp, []).append(rec)

    # ── Processar cada LP ────────────────────────────────────────────────────
    resultados: list[dict] = []
    lps_sem_referencia: list[str] = []

    for lp_codigo, ct2_recs in sorted(ct2_por_lp.items()):
        ref = ct5_ref.get(lp_codigo)
        descricao = (ct2_recs[0].get("ct5_desc") or "").strip() if ct2_recs else ""
        if not descricao and ref:
            descricao = ref.descricao or ""

        if ref is None or not ref.chave_busca:
            lps_sem_referencia.append(lp_codigo)
            total_ct2 = sum(float(r.get("debito") or 0) for r in ct2_recs)
            resultados.append({
                "lp_codigo": lp_codigo,
                "descricao": descricao,
                "status": "sem_mapeamento",
                "total_ct2": round(total_ct2, 2),
                "total_sft": None,
                "diferenca": None,
                "qt_ct2": len(ct2_recs),
                "qt_sft": 0,
                "detalhes": [],
            })
            continue

        try:
            campos = _parse_chave_busca(ref.chave_busca)
        except Exception as exc:
            logger.warning("LP %s: erro ao parsear chave_busca=%s: %s", lp_codigo, ref.chave_busca, exc)
            lps_sem_referencia.append(lp_codigo)
            continue

        # Índice CT2: chave_parcial → registros
        ct2_idx: dict[str, list[dict]] = {}
        for rec in ct2_recs:
            chave = _extrair_parcial_de_ct2key(str(rec.get("ct2_key") or ""), campos)
            ct2_idx.setdefault(chave, []).append(rec)

        # Índice SFT: chave_parcial → registros (calculado para este LP)
        sft_idx: dict[str, list[dict]] = {}
        for sft in sft_data:
            chave = _construir_chave_sft(sft, campos)
            if chave:  # ignora registros SFT que não produzem chave para este LP
                sft_idx.setdefault(chave, []).append(sft)

        todas_chaves = sorted(set(ct2_idx) | set(sft_idx))
        detalhes: list[dict] = []
        total_ct2 = 0.0
        total_sft = 0.0

        for chave in todas_chaves:
            ct2_list = ct2_idx.get(chave, [])
            sft_list = sft_idx.get(chave, [])

            val_ct2 = sum(float(r.get("debito") or 0) for r in ct2_list)
            val_sft = sum(float(s.get("valcont") or 0) for s in sft_list)
            diferenca = round(val_ct2 - val_sft, 2)

            total_ct2 += val_ct2
            total_sft += val_sft

            if not ct2_list:
                status = "so_sft"
            elif not sft_list:
                status = "so_ct2"
            elif abs(diferenca) <= 0.01:
                status = "ok"
            else:
                status = "diferente"

            # Info de NF para exibição
            nf = ""
            if sft_list:
                nf = str(sft_list[0].get("nf") or "").strip()
            elif ct2_list:
                # Tenta extrair NF do CT2_KEY pela posição D1_DOC
                raw_key = str(ct2_list[0].get("ct2_key") or "")
                for campo, tam in campos:
                    if campo in ("D1_DOC", "F1_DOC"):
                        nf = raw_key[sum(t for _, t in campos[:campos.index((campo, tam))]):sum(t for _, t in campos[:campos.index((campo, tam))]) + tam].strip()
                        break

            detalhes.append({
                "chave": chave,
                "nf": nf,
                "qt_ct2": len(ct2_list),
                "qt_sft": len(sft_list),
                "val_ct2": round(val_ct2, 2),
                "val_sft": round(val_sft, 2),
                "diferenca": diferenca,
                "status": status,
            })

        total_diferenca = round(total_ct2 - total_sft, 2)
        lp_status = "ok" if abs(total_diferenca) <= 0.01 else "diferente"

        resultados.append({
            "lp_codigo": lp_codigo,
            "descricao": descricao,
            "status": lp_status,
            "total_ct2": round(total_ct2, 2),
            "total_sft": round(total_sft, 2),
            "diferenca": total_diferenca,
            "qt_ct2": len(ct2_recs),
            "qt_sft": sum(len(v) for v in sft_idx.values()),
            "detalhes": detalhes,
        })

    # ── Resumo ───────────────────────────────────────────────────────────────
    total_ok = sum(1 for r in resultados if r["status"] == "ok")
    total_dif = sum(1 for r in resultados if r["status"] == "diferente")
    total_sem = sum(1 for r in resultados if r["status"] == "sem_mapeamento")

    return {
        "empresa_id": empresa_id,
        "carga_id_ct2": carga_id_ct2,
        "carga_id_sft": carga_id_sft,
        "params_ct2": carga_ct2.parametros_json,
        "params_sft": carga_sft.parametros_json,
        "resumo": {
            "total_lps": len(resultados),
            "ok": total_ok,
            "diferente": total_dif,
            "sem_mapeamento": total_sem,
            "total_ct2": round(sum(r["total_ct2"] for r in resultados if r["total_ct2"] is not None), 2),
            "total_sft": round(sum(r["total_sft"] for r in resultados if r["total_sft"] is not None), 2),
        },
        "lps_sem_referencia": lps_sem_referencia,
        "resultados": resultados,
    }
