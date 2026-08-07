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

from core.data_base import parse_ano_mes
from models.protheus_carga import ProtheusCarga, ProtheusCargaRegistro
from models.lancamento_padrao import LancamentoPadrao
from services import analise_ia_service, matching_manual_fiscal_service
from tools.fiscal.match_ct2_sft import match_ct2_sft as _match_ct2_sft_impl

logger = logging.getLogger(__name__)

# Mesmo padrao usado em tools/fiscal/match_ct2_sft.py para extrair o numero
# da NF/CT-e de historicos de razao como "DEVOLUCAO COMPRA NFE 2202566".
_NF_HISTORICO_RE = re.compile(r"(?:NFE?|CTE)\.?\s*(\d+)", re.IGNORECASE)


def _nf_normalizada(valor) -> str:
    return re.sub(r"^0+(?=\d)", "", str(valor or "").strip())


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


# LPs que concentram as notas de Entrada (650, 641, 640) ou Saida (610) -- usado
# quando tipo_mov e informado, independente da sequencia do LP.
_LP_CODIGO_POR_TIPO_MOV = {"ENTRADA": {"650", "641", "640"}, "SAIDA": {"610"}}


def conferir(
    db: Session,
    empresa_id: int,
    carga_id_ct2: int | None = None,
    carga_id_sft: int | None = None,
    tipo_mov: str | None = None,
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

    # ── Filtro Entrada/Saida: restringe aos LPs 650/641/640 (entrada) ou 610 ──
    # (saida), independente da sequencia. Aplicado aqui, antes de qualquer
    # indexacao do SFT ou processamento de grupo/individual, para que o SFT
    # considerado na conferencia ja saia restrito aos CFOPs/TES desses LPs.
    #
    # LPs de OUTRO lp_codigo que compartilham "grupo" com algum LP filtrado
    # tambem precisam ficar: um grupo (ex.: "USO CONSUMO") pode juntar LP 650
    # (entrada geral) com LP 651 (rateio) -- restringir so' pelos lp_codigo
    # exatos jogaria fora o 651 mesmo com o agrupamento configurado, fazendo
    # notas ja lancadas (so' que via 651) aparecerem como divergentes.
    tipo_mov_norm = (tipo_mov or "").strip().upper()
    lp_codigos_filtro = _LP_CODIGO_POR_TIPO_MOV.get(tipo_mov_norm)
    if lp_codigos_filtro:
        grupos_do_filtro = {lp.grupo for lp in todos_lps if lp.lp_codigo in lp_codigos_filtro and lp.grupo}
        todos_lps = [
            lp for lp in todos_lps
            if lp.lp_codigo in lp_codigos_filtro or (lp.grupo and lp.grupo in grupos_do_filtro)
        ]

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

    # Com o filtro Entrada/Saida ativo, descarta do CT2 qualquer lancamento de
    # LP fora da lista permitida (lp_codigos_filtro + LPs do mesmo grupo, ja
    # resolvidos acima em todos_lps) -- sem isso eles cairiam como
    # "sem_mapeamento" (LP sem config carregada) em vez de simplesmente nao
    # entrar na conferencia.
    if lp_codigos_filtro:
        lp_codigos_permitidos = {lp.lp_codigo for lp in todos_lps}
        ct2_data = [r for r in ct2_data if str(r.get("ct2_lp") or "").strip() in lp_codigos_permitidos]

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

    # ── Helper para calcular o "valor do SFT" usado na comparacao/matching ──
    # Por padrao soma FT_VALCONT; se o LP tiver colunas_valor_sft configurado,
    # soma essas colunas no lugar (ex.: ["difal", "vfcpdif"]).
    def _valor_sft(registro: dict, colunas: list[str] | None) -> float:
        if not colunas:
            return float(registro.get("valcont") or 0)
        return sum(float(registro.get(c) or 0) for c in colunas)

    def _aplicar_valor_calc(sft_lp: list[dict], colunas: list[str] | None) -> list[dict]:
        return [{**s, "_valor_calc": _valor_sft(s, colunas)} for s in sft_lp]

    # ── Helper para filtrar SFT dado cfops_set e tes_set ────────────────────
    def _limpar_set(valores):
        cleaned = {str(v).strip() for v in (valores or []) if str(v).strip()}
        return cleaned or None

    def _filtrar_sft(
        cfops_set, tes_set, cfops_excluir_set=None, tes_excluir_set=None,
        especies_set=None, especies_excluir_set=None, series_set=None,
    ):
        cfops_aceitos = _limpar_set(cfops_set)
        cfops_rejeitados = _limpar_set(cfops_excluir_set)
        tes_rejeitadas = _limpar_set(tes_excluir_set)
        especies_aceitas = _limpar_set(especies_set)
        especies_rejeitadas = _limpar_set(especies_excluir_set)
        series_aceitas = _limpar_set(series_set)
        # LP sem CFOP configurado (ex.: servicos/NFS-e, que nao tem CFOP no SFT)
        # -- sem restricao de CFOP, varre o SFT completo. sft_por_cfop indexa
        # so' os registros com cfop preenchido, entao os "sem cfop" (ex.:
        # especie=LOC) ficariam de fora se usassemos so' esse indice aqui.
        origem = (
            sft_data if cfops_aceitos is None
            else [s for cfop, lst in sft_por_cfop.items() if any(c in cfop for c in cfops_aceitos) for s in lst]
        )
        return [
            s for s in origem
            if cfops_rejeitados is None or not any(c in str(s.get("cfop") or "").strip() for c in cfops_rejeitados)
            if tes_set is None or any(t in str(s.get("tes") or "").strip() for t in tes_set)
            if tes_rejeitadas is None or not any(t in str(s.get("tes") or "").strip() for t in tes_rejeitadas)
            if especies_aceitas is None or any(e in str(s.get("especie") or "").strip() for e in especies_aceitas)
            if especies_rejeitadas is None or not any(e in str(s.get("especie") or "").strip() for e in especies_rejeitadas)
            if series_aceitas is None or any(sr in str(s.get("serie") or "").strip() for sr in series_aceitas)
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
        # Regex 3: historico de Saida (ex.: "VENDA PROD NFE12064 RM 001778",
        # "ICMS DEBITADO NFE 12064") nao comeca com "NF " -- mesmo padrao
        # tolerante usado em tools/fiscal/match_ct2_sft.py, busca em qualquer
        # posicao da string. Sem filial embutido, mesma resolucao do regex 2.
        _HIST_RE_NF_TOLERANTE = re.compile(r"(?:NFE?|CTE)\.?\s*(\d+)", re.IGNORECASE)

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
            valcont = round(float(s.get("_valor_calc", s.get("valcont")) or 0), 2)
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
            m_nf = _HIST_RE_NF.match(hist) or _HIST_RE_NF_TOLERANTE.search(hist)
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
        return _match_ct2_sft_impl(ct2_recs, sft_recs, campo_valor_sft="_valor_calc", tolerancia=0.10)

    # ── Matches manuais ja confirmados (ver matching_manual_fiscal_service) ──
    # Casos em que o CT2_KEY veio vazio do Protheus e o algoritmo automatico
    # nao teve como desambiguar sozinho (mais de um fornecedor candidato na
    # mesma NF/filial/data). Busca uma vez para o periodo inteiro e agrupa por
    # (lp_codigo, descricao) -- grupo usa lp_codigo=None e descricao=nome do
    # grupo, LP individual usa (lp_codigo, descricao) igual ao resto da tela.
    ano_periodo, mes_periodo = parse_ano_mes(carga_ct2.data_base)
    periodo = f"{ano_periodo}-{mes_periodo:02d}"
    matches_manuais_por_contexto: dict[tuple, list] = {}
    for m in matching_manual_fiscal_service.listar(db, empresa_id=empresa_id, tipo="pre_conferencia", periodo=periodo):
        matches_manuais_por_contexto.setdefault((m.lp_codigo, m.lp_descricao), []).append(m)

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
        cfops_excluir_parts: list[str] = []
        tes_excluir_parts: list[str] = []
        especies_parts: list[str] = []
        especies_excluir_parts: list[str] = []
        series_parts: list[str] = []
        colunas_valor_set: set[str] = set()
        has_filtro = False
        for m in members:
            if m.cfops:
                has_filtro = True
                cfops_set.update(str(c).strip() for c in m.cfops)
            if m.tes_codes:
                has_filtro = True
                tes_parts.extend(str(t).strip() for t in m.tes_codes)
            if m.cfops_excluir:
                cfops_excluir_parts.extend(str(c).strip() for c in m.cfops_excluir)
            if m.tes_codes_excluir:
                tes_excluir_parts.extend(str(t).strip() for t in m.tes_codes_excluir)
            if m.especies:
                has_filtro = True
                especies_parts.extend(str(e).strip() for e in m.especies)
            if m.especies_excluir:
                especies_excluir_parts.extend(str(e).strip() for e in m.especies_excluir)
            if m.series:
                has_filtro = True
                series_parts.extend(str(sr).strip() for sr in m.series)
            if m.colunas_valor_sft:
                colunas_valor_set.update(str(c).strip() for c in m.colunas_valor_sft)
        tes_set = set(tes_parts) if tes_parts else None
        cfops_excluir_set = set(cfops_excluir_parts) if cfops_excluir_parts else None
        tes_excluir_set = set(tes_excluir_parts) if tes_excluir_parts else None
        especies_set = set(especies_parts) if especies_parts else None
        especies_excluir_set = set(especies_excluir_parts) if especies_excluir_parts else None
        series_set = set(series_parts) if series_parts else None
        colunas_valor_grupo = sorted(colunas_valor_set) if colunas_valor_set else None

        if not has_filtro:
            # Grupo sem nenhum filtro (CFOP/TES/Especie/Serie) configurado --
            # nao ha' como restringir o SFT, nao aparece na pre-conferencia
            # (so' entra no resumo "sem_mapeamento" via lps_sem_cfop).
            lps_sem_cfop.append(grupo_nome)
            continue

        sft_lp = _filtrar_sft(cfops_set, tes_set, cfops_excluir_set, tes_excluir_set, especies_set, especies_excluir_set, series_set)
        sft_lp = _aplicar_valor_calc(sft_lp, colunas_valor_grupo)
        total_sft = round(sum(s["_valor_calc"] for s in sft_lp), 2)
        diferenca = round(total_ct2 - total_sft, 2)

        ct2_matched, sft_matched = _match_ct2_sft(ct2_recs, sft_lp)

        matches_deste = matches_manuais_por_contexto.get((None, grupo_nome), [])
        matches_manuais_aplicados: list = []
        if matches_deste:
            ct2_matched, sft_matched, matches_manuais_aplicados = matching_manual_fiscal_service.aplicar_matches_manuais(
                ct2_matched, sft_matched, matches_deste, campo_valor_ct2="debito", campo_valor_sft="_valor_calc",
            )

        nf_cruzamento = _nf_cruzamento(ct2_recs, sft_lp)

        ct2_detalhes = sorted(
            [{"data": str(r.get("data") or ""), "lote": str(r.get("lote_sub_doc_linha") or ""),
              "historico": str(r.get("historico") or "")[:80], "debito": round(float(r.get("debito") or 0), 2),
              "credito": round(float(r.get("credito") or 0), 2), "conta": str(r.get("conta") or ""),
              "matched": r["matched"], "matched_manual": r.get("matched_manual", False)}
             for r in ct2_matched],
            key=lambda x: x["data"],
        )
        sft_detalhes = sorted(
            [{"filial": str(s.get("filial") or ""), "nf": str(s.get("nf") or ""),
              "emissao": str(s.get("entrada") or s.get("emissao") or ""), "cliefor": str(s.get("cliefor") or ""),
              "cfop": str(s.get("cfop") or ""), "tes": str(s.get("tes") or ""),
              "valcont": round(float(s.get("valcont") or 0), 2),
              "valor_calculado": round(float(s.get("_valor_calc", s.get("valcont")) or 0), 2),
              "matched": s["matched"], "matched_manual": s.get("matched_manual", False)}
             for s in sft_matched],
            key=lambda x: (x["filial"], x["nf"]),
        )
        resultados.append({
            "lp_codigo": lp_codigo_display, "descricao": grupo_nome, "is_grupo": True,
            "status": "ok" if abs(diferenca) <= 0.01 else "diferente",
            "total_ct2": total_ct2, "total_sft": total_sft, "diferenca": diferenca,
            "qt_ct2": len(ct2_recs), "qt_sft": len(sft_lp),
            "ct2_detalhes": ct2_detalhes, "sft_detalhes": sft_detalhes,
            "matches_manuais_aplicados": matches_manuais_aplicados,
            "nf_cruzamento": nf_cruzamento,
        })

    # ── Processar INDIVIDUAIS (sem grupo) ────────────────────────────────────
    for (lp_codigo, descricao), ct2_recs in sorted(ct2_individual.items()):
        config = lp_configs.get((lp_codigo, descricao))

        total_ct2 = round(sum(float(r.get("debito") or 0) for r in ct2_recs), 2)

        if not descricao and config and config.descricao:
            descricao = config.descricao

        if not config or not (config.cfops or config.tes_codes or config.especies or config.series):
            # LP sem nenhum filtro (CFOP/TES/Especie/Serie) configurado -- nao
            # ha' como restringir o SFT, nao aparece na pre-conferencia (so'
            # entra no resumo "sem_mapeamento" via lps_sem_cfop).
            lps_sem_cfop.append(f"{lp_codigo} {descricao}".strip())
            continue

        cfops_set = {str(c).strip() for c in config.cfops} if config.cfops else set()
        tes_set = {str(t).strip() for t in config.tes_codes} if config.tes_codes else None
        cfops_excluir_set = {str(c).strip() for c in config.cfops_excluir} if config.cfops_excluir else None
        tes_excluir_set = {str(t).strip() for t in config.tes_codes_excluir} if config.tes_codes_excluir else None
        especies_set = {str(e).strip() for e in config.especies} if config.especies else None
        especies_excluir_set = {str(e).strip() for e in config.especies_excluir} if config.especies_excluir else None
        series_set = {str(sr).strip() for sr in config.series} if config.series else None
        colunas_valor_lp = [str(c).strip() for c in config.colunas_valor_sft] if config.colunas_valor_sft else None
        sft_lp = _filtrar_sft(cfops_set, tes_set, cfops_excluir_set, tes_excluir_set, especies_set, especies_excluir_set, series_set)
        sft_lp = _aplicar_valor_calc(sft_lp, colunas_valor_lp)

        total_sft = round(sum(s["_valor_calc"] for s in sft_lp), 2)
        diferenca = round(total_ct2 - total_sft, 2)
        lp_status = "ok" if abs(diferenca) <= 0.01 else "diferente"

        ct2_matched, sft_matched = _match_ct2_sft(ct2_recs, sft_lp)

        matches_deste = matches_manuais_por_contexto.get((lp_codigo, descricao), [])
        matches_manuais_aplicados: list = []
        if matches_deste:
            ct2_matched, sft_matched, matches_manuais_aplicados = matching_manual_fiscal_service.aplicar_matches_manuais(
                ct2_matched, sft_matched, matches_deste, campo_valor_ct2="debito", campo_valor_sft="_valor_calc",
            )

        nf_cruzamento = _nf_cruzamento(ct2_recs, sft_lp)

        ct2_detalhes = sorted(
            [{"data": str(r.get("data") or ""), "lote": str(r.get("lote_sub_doc_linha") or ""),
              "historico": str(r.get("historico") or "")[:80], "debito": round(float(r.get("debito") or 0), 2),
              "credito": round(float(r.get("credito") or 0), 2), "conta": str(r.get("conta") or ""),
              "matched": r["matched"], "matched_manual": r.get("matched_manual", False)}
             for r in ct2_matched],
            key=lambda x: x["data"],
        )
        sft_detalhes = sorted(
            [{"filial": str(s.get("filial") or ""), "nf": str(s.get("nf") or ""),
              "emissao": str(s.get("entrada") or s.get("emissao") or ""), "cliefor": str(s.get("cliefor") or ""),
              "cfop": str(s.get("cfop") or ""), "tes": str(s.get("tes") or ""),
              "valcont": round(float(s.get("valcont") or 0), 2),
              "valor_calculado": round(float(s.get("_valor_calc", s.get("valcont")) or 0), 2),
              "matched": s["matched"], "matched_manual": s.get("matched_manual", False)}
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
            "matches_manuais_aplicados": matches_manuais_aplicados,
            "qt_ct2":       len(ct2_recs),
            "qt_sft":       len(sft_lp),
            "ct2_detalhes": ct2_detalhes,
            "sft_detalhes": sft_detalhes,
            "nf_cruzamento": nf_cruzamento,
        })

    # ── Resumo ───────────────────────────────────────────────────────────────
    total_ok  = sum(1 for r in resultados if r["status"] == "ok")
    total_dif = sum(1 for r in resultados if r["status"] == "diferente")
    total_sem = len(lps_sem_cfop)  # nao entram em resultados, so' no resumo

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


def analisar_divergencia(
    db: Session,
    empresa_id: int,
    lp_codigo: str,
    descricao: str,
    carga_id_ct2: int | None = None,
    carga_id_sft: int | None = None,
    tipo_mov: str | None = None,
) -> dict:
    """
    Diagnostico de por que um LP/grupo com status "diferente" nao casou
    (botao "Analisar com IA" na Pre-Conferencia). Reaproveita o resultado de
    conferir() para nao duplicar a logica de matching/filtro, busca no SFT
    completo (sem o filtro de CFOP/TES/Especie do LP) as notas referentes aos
    lancamentos CT2 nao conciliados, e envia tudo pra engine de diagnostico
    em smartconciliacoes_ia.
    """
    resultado_completo = conferir(db, empresa_id, carga_id_ct2, carga_id_sft, tipo_mov)
    alvo = next(
        (
            r for r in resultado_completo["resultados"]
            if r["lp_codigo"] == lp_codigo and (r["descricao"] or "") == (descricao or "")
        ),
        None,
    )
    if not alvo:
        raise HTTPException(404, f"LP {lp_codigo} / {descricao!r} nao encontrado no resultado da conferencia.")

    registros_nao_conciliados_a = [d for d in alvo["ct2_detalhes"] if not d["matched"]]
    registros_nao_conciliados_b = [d for d in alvo.get("sft_detalhes", []) if not d.get("matched")]

    if alvo.get("is_grupo"):
        membros = (
            db.query(LancamentoPadrao)
            .filter(LancamentoPadrao.empresa_id == empresa_id, LancamentoPadrao.grupo == descricao)
            .all()
        )
    else:
        membros = (
            db.query(LancamentoPadrao)
            .filter(
                LancamentoPadrao.empresa_id == empresa_id,
                LancamentoPadrao.lp_codigo == lp_codigo,
                LancamentoPadrao.descricao == descricao,
            )
            .all()
        )

    cfops, tes_codes, especies = set(), set(), set()
    cfops_excluir, tes_excluir, especies_excluir = set(), set(), set()
    for m in membros:
        cfops.update(m.cfops or [])
        tes_codes.update(m.tes_codes or [])
        especies.update(m.especies or [])
        cfops_excluir.update(m.cfops_excluir or [])
        tes_excluir.update(m.tes_codes_excluir or [])
        especies_excluir.update(m.especies_excluir or [])
    config = {
        "cfops": sorted(cfops), "cfops_excluir": sorted(cfops_excluir),
        "tes_codes": sorted(tes_codes), "tes_codes_excluir": sorted(tes_excluir),
        "especies": sorted(especies), "especies_excluir": sorted(especies_excluir),
    }

    # Candidatos brutos: busca no SFT completo (sem o filtro de CFOP/TES/Especie
    # do LP) pelas NFs extraidas do historico dos lancamentos CT2 nao conciliados
    # -- mesma investigacao manual: a nota pode existir, so' nao entrar no
    # conjunto candidato por causa de um CFOP/TES/Especie nao configurado.
    sft_data = _carregar_dados_carga(db, resultado_completo["carga_id_sft"])
    nfs_buscadas = set()
    for d in registros_nao_conciliados_a:
        m = _NF_HISTORICO_RE.search(d.get("historico") or "")
        if m:
            nfs_buscadas.add(_nf_normalizada(m.group(1)))
    candidatos_brutos_b = [s for s in sft_data if _nf_normalizada(s.get("nf")) in nfs_buscadas]

    # Diagnostico de qualidade da carga CT2 -- detecta problemas de parametro
    # (saldo errado, ct2_lp vazio, lote restrictivo) que causam total_ct2 = 0
    # mesmo com registros presentes na carga.
    ct2_data_all = _carregar_dados_carga(db, resultado_completo["carga_id_ct2"])
    total_carga = len(ct2_data_all)
    debito_zero = sum(1 for r in ct2_data_all if float(r.get("debito") or 0) == 0)
    ct2_lp_vazio = sum(1 for r in ct2_data_all if not str(r.get("ct2_lp") or "").strip())
    contagem_lp: dict[str, int] = {}
    for r in ct2_data_all:
        lp_val = str(r.get("ct2_lp") or "").strip() or "(vazio)"
        contagem_lp[lp_val] = contagem_lp.get(lp_val, 0) + 1
    top_lps = sorted(contagem_lp.items(), key=lambda x: -x[1])[:10]

    params_ct2 = resultado_completo.get("params_ct2") or {}
    saldo_usado = str(params_ct2.get("saldo") or "1")
    saldo_desc = {"1": "Ambos (debito e credito)", "2": "Somente Debito", "3": "Somente Credito"}.get(saldo_usado, saldo_usado)
    lote_usado = str(params_ct2.get("lote") or "008810 (default)")

    diagnostico_carga = {
        "total_registros_carga": total_carga,
        "registros_debito_zero": debito_zero,
        "pct_debito_zero": round(debito_zero / total_carga * 100, 1) if total_carga else 0,
        "registros_ct2_lp_vazio": ct2_lp_vazio,
        "pct_ct2_lp_vazio": round(ct2_lp_vazio / total_carga * 100, 1) if total_carga else 0,
        "top_ct2_lp": [{"lp": lp, "quantidade": qt} for lp, qt in top_lps],
        "parametros_usados": {
            "saldo": saldo_usado,
            "saldo_descricao": saldo_desc,
            "lote": lote_usado,
            "conta_de": params_ct2.get("conta_de"),
            "conta_ate": params_ct2.get("conta_ate"),
            "data_ini": params_ct2.get("data_ini"),
            "data_fim": params_ct2.get("data_fim"),
        },
        "alertas": [
            *(["SALDO=3 (Somente Credito): todos os registros tem debito=0 — a carga nao traz lancamentos de debito, logo total_ct2 sera sempre 0 para todos os LPs."]
              if saldo_usado == "3" else []),
            *(["SALDO=1 (Ambos): a carga inclui lancamentos de credito (debito=0) e debito. Se o total_ct2 de um LP e 0, os lancamentos desse LP podem estar do lado credito da particao (conta_de/ate errada)."]
              if saldo_usado == "1" else []),
            *(["CT2_LP VAZIO NA MAIORIA DOS REGISTROS: o campo ct2_lp esta em branco para mais de 80% dos registros — a carga trouxe lancamentos que nao tem Lancamento Padrao vinculado no Protheus (CT2_ORIGEM nao bateu com nenhum CT5)."]
              if total_carga and ct2_lp_vazio / total_carga > 0.8 else []),
        ],
    }

    payload = {
        "dominio": "fiscal",
        "empresa_id": empresa_id,
        "contexto": {
            "lp_codigo": lp_codigo,
            "descricao": descricao,
            "status": alvo["status"],
            "total_ct2": alvo["total_ct2"],
            "total_sft": alvo["total_sft"],
            "diferenca": alvo["diferenca"],
            "qt_ct2": alvo["qt_ct2"],
            "qt_sft": alvo["qt_sft"],
        },
        "registros_nao_conciliados_a": registros_nao_conciliados_a,
        "registros_nao_conciliados_b": registros_nao_conciliados_b,
        "rotulo_a": "CT2 (razao)",
        "rotulo_b": "SFT (livro fiscal)",
        "config": config,
        "candidatos_brutos_b": candidatos_brutos_b,
        "diagnostico_carga": diagnostico_carga,
        "gerar_explicacao_ia": True,
    }

    return analise_ia_service.chamar_diagnostico(payload)


def diagnosticar_nota(
    db: Session,
    empresa_id: int,
    nf: str,
    cliefor: str,
    filial: str,
    valor: float,
    carga_id_ct2: int | None = None,
    carga_id_sft: int | None = None,
) -> dict:
    """
    Diagnostica por que uma nota fiscal especifica do SFT nao casou com nenhum
    lancamento CT2. Busca a NF na carga CT2 (via ct2_key e historico) e classifica
    o motivo: ausente, lote errado, filial/cliefor/valor divergente, ct2_lp vazio.
    Chama o smartconciliacoes_ia para gerar explicacao em linguagem natural.
    """
    # ── Resolve carga CT2 ────────────────────────────────────────────────────
    if carga_id_ct2 is None:
        carga_ct2 = _ultima_carga(db, empresa_id, "CT2RAZCT5")
        if not carga_ct2:
            raise HTTPException(404, "Nenhuma carga CT2RAZCT5 concluida encontrada.")
        carga_id_ct2 = carga_ct2.id
    else:
        carga_ct2 = db.query(ProtheusCarga).get(carga_id_ct2)
        if not carga_ct2 or carga_ct2.empresa_id != empresa_id:
            raise HTTPException(404, f"Carga CT2RAZCT5 {carga_id_ct2} nao encontrada.")

    params_ct2 = carga_ct2.parametros_json or {}
    lote_carga = str(params_ct2.get("lote") or "008810")
    saldo_carga = str(params_ct2.get("saldo") or "1")
    saldo_desc = {"1": "Ambos", "2": "Somente Debito", "3": "Somente Credito"}.get(saldo_carga, saldo_carga)
    data_ini = str(params_ct2.get("data_ini") or "")
    data_fim = str(params_ct2.get("data_fim") or "")

    # ── Normaliza chaves de busca ────────────────────────────────────────────
    nf_norm = re.sub(r"^0+(?=\d)", "", nf.strip())
    filial_norm = filial.strip().zfill(4) if filial.strip() else ""
    cliefor_s = cliefor.strip()
    cliefor_norm = (cliefor_s[:6].zfill(6) if len(cliefor_s) >= 6 else cliefor_s.zfill(6))

    # ── Carrega registros CT2 ────────────────────────────────────────────────
    ct2_data = _carregar_dados_carga(db, carga_id_ct2)

    # Regex tolerante: "NFE315", "NFE 315", "NF 315", "NF315", "000000315"
    _nf_re = re.compile(
        r"(?:NFE?|CTE|NF)\s*\.?\s*0*" + re.escape(nf_norm) + r"(?!\d)",
        re.IGNORECASE,
    )

    encontrados_key: list[dict] = []
    encontrados_hist: list[dict] = []

    for rec in ct2_data:
        k = str(rec.get("ct2_key") or "").strip()
        # Busca via ct2_key (posicoes 4:13 = NF)
        if len(k) >= 13:
            k_nf = re.sub(r"^0+(?=\d)", "", k[4:13].strip())
            if k_nf == nf_norm:
                encontrados_key.append(rec)
                continue
        # Busca via historico
        hist = str(rec.get("historico") or "")
        if _nf_re.search(hist):
            encontrados_hist.append(rec)

    encontrados = encontrados_key + encontrados_hist

    # ── Monta diagnostico ────────────────────────────────────────────────────
    parametros_carga = {
        "lote": lote_carga,
        "saldo": saldo_carga,
        "saldo_descricao": saldo_desc,
        "data_ini": data_ini,
        "data_fim": data_fim,
        "conta_de": params_ct2.get("conta_de") or "",
        "conta_ate": params_ct2.get("conta_ate") or "",
    }

    if not encontrados:
        alertas = [
            f"Lote filtrado na carga: {lote_carga} — se o lancamento desta NF esta em outro lote, nao aparece nesta carga.",
        ]
        if saldo_carga == "3":
            alertas.append("SALDO=3 (Somente Credito): a carga nao traz lancamentos de debito — confirme o parametro saldo ao recarregar.")
        diagnostico = {
            "encontrada": False,
            "motivo": "ausente_na_carga",
            "descricao": f"NF {nf_norm} nao encontrada em nenhum registro da carga CT2 {carga_id_ct2} (buscada via ct2_key e historico).",
            "parametros_carga": parametros_carga,
            "alertas": alertas,
        }
    else:
        registros_analisados = []
        for rec in encontrados:
            k = str(rec.get("ct2_key") or "").strip()
            debito = round(float(rec.get("debito") or 0), 2)
            ct2_lp = str(rec.get("ct2_lp") or "").strip()
            hist = str(rec.get("historico") or "")[:120]
            via = "ct2_key" if rec in encontrados_key else "historico"

            rec_filial = ""
            rec_cliefor = ""
            if len(k) >= 22:
                rec_filial = k[0:4].strip().zfill(4)
                raw_cf = k[16:22].strip()
                rec_cliefor = (raw_cf[:6].zfill(6) if len(raw_cf) >= 6 else raw_cf.zfill(6))

            problemas: list[str] = []
            if rec_filial and filial_norm and rec_filial != filial_norm:
                problemas.append(f"filial difere: CT2={rec_filial}, SFT={filial_norm}")
            if rec_cliefor and cliefor_norm and rec_cliefor != cliefor_norm:
                problemas.append(f"cliefor difere: CT2={rec_cliefor}, SFT={cliefor_norm}")
            if debito > 0 and abs(debito - valor) > 0.10:
                problemas.append(f"valor difere: CT2={debito:.2f}, SFT={valor:.2f}")
            if not ct2_lp:
                problemas.append("ct2_lp vazio: lancamento sem LP vinculado — nao aparece em nenhum LP da conferencia")
            if via == "historico" and len(k) < 13:
                problemas.append("sem ct2_key valida: matching depende do historico (menos preciso)")

            registros_analisados.append({
                "via": via,
                "ct2_key": k,
                "historico": hist,
                "debito": debito,
                "ct2_lp": ct2_lp,
                "problemas": problemas,
            })

        tem_problema = any(r["problemas"] for r in registros_analisados)
        diagnostico = {
            "encontrada": True,
            "total_encontrados": len(encontrados),
            "motivo": "encontrado_com_divergencia" if tem_problema else "encontrado_sem_problema_aparente",
            "descricao": (
                f"NF {nf_norm} encontrada em {len(encontrados)} registro(s) da carga CT2, "
                "mas com divergencias que impediram o matching."
                if tem_problema else
                f"NF {nf_norm} encontrada em {len(encontrados)} registro(s) — sem divergencias obvias detectadas; "
                "o matching pode ter falhado por ambiguidade de fornecedor ou NF duplicada entre filiais."
            ),
            "registros": registros_analisados,
            "parametros_carga": parametros_carga,
            "alertas": [],
        }

    # ── Chama IA para explicacao ─────────────────────────────────────────────
    payload_ia = {
        "nf": nf_norm,
        "filial_sft": filial,
        "cliefor_sft": cliefor,
        "valor_sft": valor,
        "carga_id_ct2": carga_id_ct2,
        "empresa_id": empresa_id,
        "diagnostico": diagnostico,
    }
    try:
        explicacao = analise_ia_service.chamar_diagnostico_nota(payload_ia)
    except Exception:
        logger.exception("Falha ao chamar IA para diagnostico de nota — retornando sem explicacao")
        explicacao = None

    return {**diagnostico, "explicacao": explicacao}
