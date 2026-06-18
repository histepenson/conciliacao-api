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
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro
from models.lancamento_padrao import LancamentoPadrao
from tools.fiscal.match_ct2_sft import match_ct2_sft as _match_ct2_sft_impl

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

    # ── Cruzamento NF: outer join CT2 × SFT agregados por NF ────────────────────
    # Retorna lista unificada com status "so_sft" | "so_ct2" | "ambos".
    # Chave normalizada: (filial:4, nf:9, cliefor) — zero-padded.
    # Origem da chave CT2:
    #   ct2_key preenchido  → CT2_KEY[0:4]/[4:13]/[16:22]
    #   ct2_key vazio c/ filial → historico "NF <nf> <nome> <filial>/<doc_orig>"
    #     → extrai (filial, nf) e resolve cliefor via SFT por valor
    #   ct2_key vazio s/ filial → historico "NF <nf> <nome>"
    #     → extrai nf e resolve (filial, cliefor) via SFT por valor
    def _nf_cruzamento(ct2_recs: list, sft_recs: list) -> list:
        # Regex 1: tem filial antes do '/' — "NF <nf> <nome> <filial>/<doc>"
        _HIST_RE_COM_FILIAL = re.compile(r'^NF\s+(\d+)\s+.*\s(\d{2,4})/', re.IGNORECASE)
        # Regex 2: só NF — "NF <nf> ..."
        _HIST_RE_NF = re.compile(r'^NF\s+(\d+)', re.IGNORECASE)

        def _norm_filial(v: str) -> str:
            return v.strip().zfill(4)

        def _norm_nf(v: str) -> str:
            return v.strip().zfill(9)

        def _norm_cliefor(v: str) -> str:
            s = re.sub(r'\s+', '', v)
            return s[:6].zfill(6) if len(s) >= 6 else s.zfill(6)

        def _norm(filial: str, nf: str, cliefor: str) -> tuple:
            return (_norm_filial(filial), _norm_nf(nf), _norm_cliefor(cliefor))

        def _chave_ct2(rec):
            k = str(rec.get("ct2_key") or "").strip()
            if len(k) < 22:
                return None
            return _norm(k[0:4], k[4:13], k[16:22])

        # ── SFT index — chaves normalizadas ──────────────────────────────────
        sft_nfs: dict = {}
        for s in sft_recs:
            filial  = str(s.get("filial")  or "").strip()
            nf      = str(s.get("nf")      or "").strip()
            cliefor = str(s.get("cliefor") or "").strip()
            if not filial or not nf:
                continue
            chave = _norm(filial, nf, cliefor)
            valcont = round(float(s.get("valcont") or 0), 2)
            emissao = str(s.get("entrada") or s.get("emissao") or "").strip()
            if chave not in sft_nfs:
                sft_nfs[chave] = {"total": 0.0, "emissao": emissao}
            sft_nfs[chave]["total"] = round(sft_nfs[chave]["total"] + valcont, 2)

        # Índices secundários para resolução por historico
        # (filial_norm, nf_norm) → lista de (cliefor_norm, total_valcont)
        sft_por_filial_nf: dict[tuple, list] = {}
        # nf_norm → lista de (filial_norm, cliefor_norm, total_valcont)
        sft_por_nf: dict[str, list] = {}
        for (filial, nf, cliefor), info in sft_nfs.items():
            total = info["total"]
            sft_por_filial_nf.setdefault((filial, nf), []).append((cliefor, total))
            sft_por_nf.setdefault(nf, []).append((filial, cliefor, total))

        if sft_nfs:
            logger.info("NF-CRUZAMENTO | sft=%d chaves | ex: %s", len(sft_nfs), list(sft_nfs.keys())[:3])
        else:
            logger.warning("NF-CRUZAMENTO | sft_nfs VAZIO — nenhum SFT com filial+nf válidos")

        def _resolver_hist(rec: dict, debito: float):
            """Resolve chave (filial, nf, cliefor) usando ct2_itemc + historico."""
            hist = str(rec.get("historico") or "").strip()
            # ct2_itemc sempre traz o fornecedor correto (CT2_ITEMC do Protheus)
            ct2_itemc = str(rec.get("ct2_itemc") or "").strip()
            cliefor_itemc = _norm_cliefor(ct2_itemc) if ct2_itemc else None

            # Tenta extrair filial + nf do historico
            m_filial = _HIST_RE_COM_FILIAL.match(hist)
            if m_filial:
                nf_norm = _norm_nf(m_filial.group(1))
                filial_norm = _norm_filial(m_filial.group(2))
                if cliefor_itemc:
                    # Chave completa: filial + nf + fornecedor do ct2_itemc
                    return (filial_norm, nf_norm, cliefor_itemc)
                # Fallback: resolver cliefor via SFT por valor
                candidatos = sft_por_filial_nf.get((filial_norm, nf_norm), [])
                exatos = [(c, t) for c, t in candidatos if abs(t - debito) <= 0.01]
                if exatos:
                    return (filial_norm, nf_norm, exatos[0][0])
                if len(candidatos) == 1:
                    return (filial_norm, nf_norm, candidatos[0][0])
                return None

            # Sem filial no historico: usa nf + ct2_itemc + SFT para filial
            m_nf = _HIST_RE_NF.match(hist)
            if m_nf:
                nf_norm = _norm_nf(m_nf.group(1))
                if cliefor_itemc:
                    # Busca filial no SFT pelo par (nf, cliefor)
                    for f, c, _ in sft_por_nf.get(nf_norm, []):
                        if c == cliefor_itemc:
                            return (f, nf_norm, cliefor_itemc)
                # Fallback por valor
                candidatos = sft_por_nf.get(nf_norm, [])
                exatos = [(f, c, t) for f, c, t in candidatos if abs(t - debito) <= 0.01]
                if exatos:
                    return (exatos[0][0], nf_norm, exatos[0][1])
                if len(candidatos) == 1:
                    return (candidatos[0][0], nf_norm, candidatos[0][1])
                return None

            return None

        # ── CT2 index ─────────────────────────────────────────────────────────
        ct2_nfs: dict = {}
        ct2_hist_ok = 0
        ct2_hist_sem_parse = 0
        ct2_hist_sem_match = 0

        for rec in ct2_recs:
            debito = round(float(rec.get("debito") or 0), 2)
            if debito == 0:
                continue
            k = str(rec.get("ct2_key") or "").strip()
            if k:
                chave = _chave_ct2(rec)
            else:
                hist_raw = str(rec.get("historico") or "").strip()
                chave = _resolver_hist(rec, debito)
                if chave is None:
                    ct2_hist_sem_parse += 1
                    logger.debug("NF-HIST SEM PARSE | hist=%r deb=%.2f", hist_raw[:120], debito)
                elif chave not in sft_nfs:
                    ct2_hist_sem_match += 1
                    logger.debug("NF-HIST SEM MATCH | chave=%s hist=%r", chave, hist_raw[:80])
                else:
                    ct2_hist_ok += 1

            if chave is None:
                continue
            ct2_nfs[chave] = round(ct2_nfs.get(chave, 0.0) + debito, 2)

        if ct2_hist_ok or ct2_hist_sem_parse or ct2_hist_sem_match:
            logger.info(
                "NF-CRUZAMENTO hist | ok=%d sem_parse=%d sem_match=%d",
                ct2_hist_ok, ct2_hist_sem_parse, ct2_hist_sem_match,
            )

        # ── Outer join ────────────────────────────────────────────────────────
        result = []
        for key in sorted(set(ct2_nfs) | set(sft_nfs), key=lambda x: (x[0], x[1])):
            f, n, c = key
            ct2_total = ct2_nfs.get(key, 0.0)
            sft_info  = sft_nfs.get(key)
            sft_total = sft_info["total"] if sft_info else 0.0
            emissao   = sft_info["emissao"] if sft_info else ""
            if ct2_total > 0 and sft_total > 0:
                status = "ambos"
            elif ct2_total > 0:
                status = "so_ct2"
            else:
                status = "so_sft"
            result.append({
                "filial": f, "nf": n, "cliefor": c, "emissao": emissao,
                "sft_total": sft_total, "ct2_total": ct2_total, "status": status,
            })

        # Validação: cada (filial, nf, cliefor) deve aparecer exatamente 1 vez.
        seen: set = set()
        for item in result:
            chave = (item["filial"], item["nf"], item["cliefor"])
            if chave in seen:
                raise ValueError(
                    f"nf_cruzamento: duplicata detectada — "
                    f"filial={item['filial']} nf={item['nf']} cliefor={item['cliefor']}"
                )
            seen.add(chave)

        return result

    # ── Matching CT2 ↔ SFT por (filial, nf, fornece) extraído de CT2_KEY ──────
    # Logica compartilhada com a conciliacao de impostos (tools/fiscal/match_ct2_sft.py)
    def _match_ct2_sft(ct2_recs: list, sft_recs: list) -> tuple:
        return _match_ct2_sft_impl(ct2_recs, sft_recs, campo_valor_sft="valcont", tolerancia=0.10)

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
            ct2_detalhes = sorted(
                [{"data": str(r.get("data") or ""), "lote": str(r.get("lote_sub_doc_linha") or ""),
                  "historico": str(r.get("historico") or "")[:80], "debito": round(float(r.get("debito") or 0), 2),
                  "credito": round(float(r.get("credito") or 0), 2), "conta": str(r.get("conta") or ""),
                  "matched": False}
                 for r in ct2_recs],
                key=lambda x: x["data"],
            )
            lps_sem_cfop.append(grupo_nome)
            resultados.append({
                "lp_codigo": lp_codigo_display, "descricao": grupo_nome, "is_grupo": True,
                "status": "sem_mapeamento", "total_ct2": total_ct2, "total_sft": None,
                "diferenca": None, "qt_ct2": len(ct2_recs), "qt_sft": 0,
                "ct2_detalhes": ct2_detalhes, "sft_detalhes": [],
                "nf_cruzamento": [],
            })
            continue

        sft_lp = _filtrar_sft(cfops_set, tes_set)
        total_sft = round(sum(float(s.get("valcont") or 0) for s in sft_lp), 2)
        diferenca = round(total_ct2 - total_sft, 2)

        ct2_matched, sft_matched = _match_ct2_sft(ct2_recs, sft_lp)
        nf_cruzamento = _nf_cruzamento(ct2_recs, sft_lp)

        ct2_detalhes = sorted(
            [{"data": str(r.get("data") or ""), "lote": str(r.get("lote_sub_doc_linha") or ""),
              "historico": str(r.get("historico") or "")[:80], "debito": round(float(r.get("debito") or 0), 2),
              "credito": round(float(r.get("credito") or 0), 2), "conta": str(r.get("conta") or ""),
              "matched": r["matched"]}
             for r in ct2_matched],
            key=lambda x: x["data"],
        )
        sft_detalhes = sorted(
            [{"filial": str(s.get("filial") or ""), "nf": str(s.get("nf") or ""),
              "emissao": str(s.get("entrada") or s.get("emissao") or ""), "cliefor": str(s.get("cliefor") or ""),
              "cfop": str(s.get("cfop") or ""), "tes": str(s.get("tes") or ""),
              "valcont": round(float(s.get("valcont") or 0), 2), "matched": s["matched"]}
             for s in sft_matched],
            key=lambda x: (x["filial"], x["nf"]),
        )
        resultados.append({
            "lp_codigo": lp_codigo_display, "descricao": grupo_nome, "is_grupo": True,
            "status": "ok" if abs(diferenca) <= 0.01 else "diferente",
            "total_ct2": total_ct2, "total_sft": total_sft, "diferenca": diferenca,
            "qt_ct2": len(ct2_recs), "qt_sft": len(sft_lp),
            "ct2_detalhes": ct2_detalhes, "sft_detalhes": sft_detalhes,
            "nf_cruzamento": nf_cruzamento,
        })

    # ── Processar INDIVIDUAIS (sem grupo) ────────────────────────────────────
    for (lp_codigo, descricao), ct2_recs in sorted(ct2_individual.items()):
        config = lp_configs.get((lp_codigo, descricao))

        total_ct2 = round(sum(float(r.get("debito") or 0) for r in ct2_recs), 2)

        if not descricao and config and config.descricao:
            descricao = config.descricao

        if not config or not config.cfops:
            ct2_detalhes = sorted(
                [{"data": str(r.get("data") or ""), "lote": str(r.get("lote_sub_doc_linha") or ""),
                  "historico": str(r.get("historico") or "")[:80], "debito": round(float(r.get("debito") or 0), 2),
                  "credito": round(float(r.get("credito") or 0), 2), "conta": str(r.get("conta") or ""),
                  "matched": False}
                 for r in ct2_recs],
                key=lambda x: x["data"],
            )
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
                "nf_cruzamento": [],
            })
            continue

        cfops_set = {str(c).strip() for c in config.cfops}
        tes_set = {str(t).strip() for t in config.tes_codes} if config.tes_codes else None
        sft_lp = _filtrar_sft(cfops_set, tes_set)

        total_sft = round(sum(float(s.get("valcont") or 0) for s in sft_lp), 2)
        diferenca = round(total_ct2 - total_sft, 2)
        lp_status = "ok" if abs(diferenca) <= 0.01 else "diferente"

        ct2_matched, sft_matched = _match_ct2_sft(ct2_recs, sft_lp)
        nf_cruzamento = _nf_cruzamento(ct2_recs, sft_lp)

        ct2_detalhes = sorted(
            [{"data": str(r.get("data") or ""), "lote": str(r.get("lote_sub_doc_linha") or ""),
              "historico": str(r.get("historico") or "")[:80], "debito": round(float(r.get("debito") or 0), 2),
              "credito": round(float(r.get("credito") or 0), 2), "conta": str(r.get("conta") or ""),
              "matched": r["matched"]}
             for r in ct2_matched],
            key=lambda x: x["data"],
        )
        sft_detalhes = sorted(
            [{"filial": str(s.get("filial") or ""), "nf": str(s.get("nf") or ""),
              "emissao": str(s.get("entrada") or s.get("emissao") or ""), "cliefor": str(s.get("cliefor") or ""),
              "cfop": str(s.get("cfop") or ""), "tes": str(s.get("tes") or ""),
              "valcont": round(float(s.get("valcont") or 0), 2), "matched": s["matched"]}
             for s in sft_matched],
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
            "nf_cruzamento": nf_cruzamento,
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
