"""
Servico de Pre Conferencia: confronta lancamentos CT2RAZCT5 com o Livro Fiscal SFT.

Fluxo:
  1. Busca a ultima carga concluida de CT2RAZCT5 e SFTENT para a empresa.
  2. Busca a configuracao de cada LP em lancamento_padrao (cfops, colunas_sft).
  3. Para cada LP:
     - Soma os debitos do CT2.
     - Filtra os registros SFT pelos CFOPs configurados para o LP.
     - Compara os totais.
"""

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro
from models.lancamento_padrao import LancamentoPadrao

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


def conferir(
    db: Session,
    empresa_id: int,
    carga_id_ct2: int | None = None,
    carga_id_sft: int | None = None,
) -> dict:
    # ── Resolucao das cargas ─────────────────────────────────────────────────
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

    # ── Configuracoes de LP ──────────────────────────────────────────────────
    todos_lps = (
        db.query(LancamentoPadrao)
        .filter(LancamentoPadrao.empresa_id == empresa_id, LancamentoPadrao.ativo.is_(True))
        .all()
    )
    lp_configs: dict[tuple[str, str], LancamentoPadrao] = {
        (lp.lp_codigo, lp.descricao or ""): lp for lp in todos_lps
    }
    # Mapeia (lp_codigo, descricao) → nome do grupo
    key_to_grupo: dict[tuple[str, str], str] = {
        (lp.lp_codigo, lp.descricao or ""): lp.grupo
        for lp in todos_lps
        if lp.grupo
    }

    # ── Dados das cargas ─────────────────────────────────────────────────────
    ct2_data = _carregar_dados_carga(db, carga_id_ct2)
    sft_data = _carregar_dados_carga(db, carga_id_sft)

    logger.info(
        "Pre-conferencia empresa=%s: ct2=%s registros (carga %s), sft=%s registros (carga %s)",
        empresa_id, len(ct2_data), carga_id_ct2, len(sft_data), carga_id_sft,
    )

    # ── Indice SFT por CFOP ──────────────────────────────────────────────────
    sft_por_cfop: dict[str, list[dict]] = {}
    for s in sft_data:
        cfop = str(s.get("cfop") or "").strip()
        if cfop:
            sft_por_cfop.setdefault(cfop, []).append(s)

    # ── Agrupar CT2 por (LP, descricao) ─────────────────────────────────────
    ct2_por_lp: dict[tuple[str, str], list[dict]] = {}
    for rec in ct2_data:
        lp = str(rec.get("ct2_lp") or "").strip()
        desc = str(rec.get("ct5_desc") or "").strip()
        if lp:
            ct2_por_lp.setdefault((lp, desc), []).append(rec)

    # ── Separar CT2: keys que pertencem a um grupo vs individuais ────────────
    ct2_por_grupo: dict[str, list[dict]] = {}
    ct2_individual: dict[tuple[str, str], list[dict]] = {}
    for key, recs in ct2_por_lp.items():
        grupo = key_to_grupo.get(key)
        if grupo:
            ct2_por_grupo.setdefault(grupo, []).extend(recs)
        else:
            ct2_individual[key] = recs

    # ── Processar cada LP ────────────────────────────────────────────────────
    resultados: list[dict] = []
    lps_sem_cfop: list[str] = []

    # ── Helper para filtrar SFT dado cfops_set e tes_set ────────────────────
    def _filtrar_sft(cfops_set, tes_set):
        return [
            s for cfop, lst in sft_por_cfop.items()
            if any(c in cfop for c in cfops_set)
            for s in lst
            if tes_set is None or any(t in str(s.get("tes") or "").strip() for t in tes_set)
        ]

    # ── Processar GRUPOS ─────────────────────────────────────────────────────
    grupos_configs: dict[str, list[LancamentoPadrao]] = {}
    for lp in todos_lps:
        if lp.grupo:
            grupos_configs.setdefault(lp.grupo, []).append(lp)

    for grupo_nome, members in sorted(grupos_configs.items()):
        ct2_recs = ct2_por_grupo.get(grupo_nome, [])
        total_ct2 = round(sum(float(r.get("debito") or 0) for r in ct2_recs), 2)
        lp_codes = sorted({m.lp_codigo for m in members})
        lp_codigo_display = lp_codes[0] if len(lp_codes) == 1 else f"{lp_codes[0]}+{len(lp_codes)-1}"

        ct2_detalhes = sorted(
            [{"data": str(r.get("data") or ""), "lote": str(r.get("lote_sub_doc_linha") or ""),
              "historico": str(r.get("historico") or "")[:80], "debito": round(float(r.get("debito") or 0), 2),
              "credito": round(float(r.get("credito") or 0), 2), "conta": str(r.get("conta") or "")}
             for r in ct2_recs],
            key=lambda x: x["data"],
        )

        cfops_set = set()
        tes_parts: list[str] = []
        has_cfops = False
        for m in members:
            if m.cfops:
                has_cfops = True
                cfops_set.update(str(c).strip() for c in m.cfops)
            if m.tes_codes:
                tes_parts.extend(str(t).strip() for t in m.tes_codes)
        tes_set = set(tes_parts) if tes_parts else None

        if not has_cfops:
            lps_sem_cfop.append(grupo_nome)
            resultados.append({
                "lp_codigo": lp_codigo_display, "descricao": grupo_nome, "is_grupo": True,
                "status": "sem_mapeamento", "total_ct2": total_ct2, "total_sft": None,
                "diferenca": None, "qt_ct2": len(ct2_recs), "qt_sft": 0,
                "ct2_detalhes": ct2_detalhes, "sft_detalhes": [],
            })
            continue

        sft_lp = _filtrar_sft(cfops_set, tes_set)
        total_sft = round(sum(float(s.get("valcont") or 0) for s in sft_lp), 2)
        diferenca = round(total_ct2 - total_sft, 2)
        sft_detalhes = sorted(
            [{"filial": str(s.get("filial") or ""), "nf": str(s.get("nf") or ""),
              "emissao": str(s.get("emissao") or ""), "cliefor": str(s.get("cliefor") or ""),
              "cfop": str(s.get("cfop") or ""), "tes": str(s.get("tes") or ""),
              "valcont": round(float(s.get("valcont") or 0), 2)} for s in sft_lp],
            key=lambda x: (x["filial"], x["nf"]),
        )
        resultados.append({
            "lp_codigo": lp_codigo_display, "descricao": grupo_nome, "is_grupo": True,
            "status": "ok" if abs(diferenca) <= 0.01 else "diferente",
            "total_ct2": total_ct2, "total_sft": total_sft, "diferenca": diferenca,
            "qt_ct2": len(ct2_recs), "qt_sft": len(sft_lp),
            "ct2_detalhes": ct2_detalhes, "sft_detalhes": sft_detalhes,
        })

    # ── Processar INDIVIDUAIS (sem grupo) ────────────────────────────────────
    for (lp_codigo, descricao), ct2_recs in sorted(ct2_individual.items()):
        config = lp_configs.get((lp_codigo, descricao))

        total_ct2 = round(sum(float(r.get("debito") or 0) for r in ct2_recs), 2)

        if not descricao and config and config.descricao:
            descricao = config.descricao

        ct2_detalhes = sorted(
            [
                {
                    "data":      str(r.get("data") or ""),
                    "lote":      str(r.get("lote_sub_doc_linha") or ""),
                    "historico": str(r.get("historico") or "")[:80],
                    "debito":    round(float(r.get("debito") or 0), 2),
                    "credito":   round(float(r.get("credito") or 0), 2),
                    "conta":     str(r.get("conta") or ""),
                }
                for r in ct2_recs
            ],
            key=lambda x: x["data"],
        )

        if not config or not config.cfops:
            lps_sem_cfop.append(f"{lp_codigo} {descricao}".strip())
            resultados.append({
                "lp_codigo":    lp_codigo,
                "descricao":    descricao,
                "status":       "sem_mapeamento",
                "total_ct2":    total_ct2,
                "total_sft":    None,
                "diferenca":    None,
                "qt_ct2":       len(ct2_recs),
                "qt_sft":       0,
                "ct2_detalhes": ct2_detalhes,
                "sft_detalhes": [],
            })
            continue

        cfops_set = {str(c).strip() for c in config.cfops}
        tes_set = {str(t).strip() for t in config.tes_codes} if config.tes_codes else None
        sft_lp = _filtrar_sft(cfops_set, tes_set)

        total_sft = round(sum(float(s.get("valcont") or 0) for s in sft_lp), 2)
        diferenca = round(total_ct2 - total_sft, 2)
        lp_status = "ok" if abs(diferenca) <= 0.01 else "diferente"

        sft_detalhes = sorted(
            [
                {
                    "filial":  str(s.get("filial") or ""),
                    "nf":      str(s.get("nf") or ""),
                    "emissao": str(s.get("emissao") or ""),
                    "cliefor": str(s.get("cliefor") or ""),
                    "cfop":    str(s.get("cfop") or ""),
                    "tes":     str(s.get("tes") or ""),
                    "valcont": round(float(s.get("valcont") or 0), 2),
                }
                for s in sft_lp
            ],
            key=lambda x: (x["filial"], x["nf"]),
        )

        resultados.append({
            "lp_codigo":    lp_codigo,
            "descricao":    descricao,
            "status":       lp_status,
            "total_ct2":    total_ct2,
            "total_sft":    total_sft,
            "diferenca":    diferenca,
            "qt_ct2":       len(ct2_recs),
            "qt_sft":       len(sft_lp),
            "ct2_detalhes": ct2_detalhes,
            "sft_detalhes": sft_detalhes,
        })

    # ── Resumo ───────────────────────────────────────────────────────────────
    total_ok  = sum(1 for r in resultados if r["status"] == "ok")
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
            "total_ct2": round(sum(r["total_ct2"] for r in resultados), 2),
            "total_sft": round(sum(r["total_sft"] for r in resultados if r["total_sft"] is not None), 2),
        },
        "lps_sem_cfop": lps_sem_cfop,
        "resultados": resultados,
    }
