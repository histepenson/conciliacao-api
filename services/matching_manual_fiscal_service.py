"""
Service de Matching Manual Fiscal.

Cobre o caso em que o matching automatico (tools/fiscal/match_ct2_sft.py) nao
consegue casar um lancamento CT2 com uma nota SFT sozinho -- tipicamente
porque o CT2_KEY/CT2_ITEMC vem vazio do Protheus (lancamento de apuracao, sem
integracao direta com a nota) e sobra mais de um fornecedor candidato na
mesma NF/filial/data, o que faz o algoritmo desistir por seguranca (evita
casar por coincidencia). Aqui o usuario confirma manualmente a
correspondencia, e essa decisao fica gravada -- com a chave CT2_KEY/ITEMC
"reconstruida" a partir dos dados da nota SFT (unica fonte confiavel de
filial/nf/fornecedor nesses casos) -- para ser reaplicada em cargas futuras
do mesmo periodo.

Usado tanto pela Conciliacao de Impostos quanto pela Pre-Conferencia.
"""

import logging
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from middleware.auth import CurrentUser
from models.matching_manual_fiscal import MatchingManualFiscal, MatchingManualFiscalItem
from schemas.matching_manual_fiscal_schema import RequestCriarMatchingManual

logger = logging.getLogger(__name__)

TOLERANCIA_REAPLICACAO = 0.01


def _norm_filial(v: Any) -> str:
    return str(v or "").strip().zfill(4)[:4]


def _norm_nf(v: Any) -> str:
    return str(v or "").strip().zfill(9)[:9]


def _norm_cliefor(v: Any) -> str:
    s = str(v or "").strip()
    return (s[:6].zfill(6) if len(s) >= 6 else s.zfill(6))


def _construir_ct2_key(filial: str, nf: str, cliefor: str) -> str:
    """
    Monta uma chave no mesmo layout do CT2_KEY nativo do Protheus (posicoes
    0:4=filial, 4:13=nf, 16:22=cliefor -- ver tools/fiscal/match_ct2_sft.py)
    a partir dos dados da nota SFT. As posicoes 13:16 (serie, nao usadas pelo
    matching de Entrada) ficam zeradas.
    """
    return f"{_norm_filial(filial)}{_norm_nf(nf)}000{_norm_cliefor(cliefor)}"


def criar(
    db: Session,
    request: RequestCriarMatchingManual,
    current_user: CurrentUser,
) -> MatchingManualFiscal:
    if request.tipo not in ("impostos", "pre_conferencia"):
        raise HTTPException(400, "tipo deve ser 'impostos' ou 'pre_conferencia'")
    if not request.itens_ct2:
        raise HTTPException(400, "Informe ao menos um lancamento do razao (itens_ct2)")
    if not request.itens_sft:
        raise HTTPException(400, "Informe ao menos uma nota do SFT (itens_sft)")

    # A nota SFT e' a fonte confiavel de filial/nf/fornecedor -- todos os
    # itens selecionados do lado SFT precisam ser da mesma nota/fornecedor,
    # senao a chave construida (filial+nf+cliefor) nao faz sentido.
    filiais = {str(s.get("filial") or "").strip() for s in request.itens_sft}
    nfs = {str(s.get("nf") or "").strip() for s in request.itens_sft}
    cliefores = {str(s.get("cliefor") or "").strip() for s in request.itens_sft}
    if len(filiais) != 1 or len(nfs) != 1 or len(cliefores) != 1:
        raise HTTPException(
            400,
            "Todos os itens do SFT selecionados devem ser da mesma nota "
            "(mesma filial, NF e fornecedor).",
        )
    filial, nf, cliefor = filiais.pop(), nfs.pop(), cliefores.pop()

    valor_total_ct2 = round(sum(float(r.get(request.campo_valor_ct2) or 0) for r in request.itens_ct2), 2)
    valor_total_sft = round(sum(float(r.get(request.campo_valor_sft) or 0) for r in request.itens_sft), 2)

    matching = MatchingManualFiscal(
        empresa_id=request.empresa_id,
        tipo=request.tipo,
        periodo=request.periodo,
        conta_contabil=request.conta_contabil,
        campo_imposto=request.campo_imposto,
        lp_codigo=request.lp_codigo,
        lp_descricao=request.lp_descricao,
        filial=filial,
        nf=nf,
        cliefor=cliefor,
        ct2_key=_construir_ct2_key(filial, nf, cliefor),
        ct2_itemc=_norm_cliefor(cliefor),
        valor_total_ct2=valor_total_ct2,
        valor_total_sft=valor_total_sft,
        observacao=request.observacao,
        usuario_id=current_user.user_id,
    )

    for rec in request.itens_ct2:
        matching.itens.append(MatchingManualFiscalItem(
            lado="ct2",
            historico=str(rec.get("historico") or "")[:200] or None,
            lote_sub_doc_linha=str(rec.get("lote_sub_doc_linha") or "")[:60] or None,
            data=str(rec.get("data") or "")[:10] or None,
            valor=round(float(rec.get(request.campo_valor_ct2) or 0), 2),
            dados_json=rec,
        ))
    for rec in request.itens_sft:
        matching.itens.append(MatchingManualFiscalItem(
            lado="sft",
            cfop=str(rec.get("cfop") or "")[:10] or None,
            especie=str(rec.get("especie") or "")[:20] or None,
            data=str(rec.get("entrada") or rec.get("emissao") or "")[:10] or None,
            valor=round(float(rec.get(request.campo_valor_sft) or 0), 2),
            dados_json=rec,
        ))

    db.add(matching)
    db.commit()
    db.refresh(matching)

    logger.info(
        "Matching manual %s criado por usuario=%s empresa=%s tipo=%s filial=%s nf=%s cliefor=%s",
        matching.id, current_user.user_id, request.empresa_id, request.tipo, filial, nf, cliefor,
    )
    return matching


def listar(
    db: Session,
    empresa_id: int,
    tipo: Optional[str] = None,
    periodo: Optional[str] = None,
    conta_contabil: Optional[str] = None,
    campo_imposto: Optional[str] = None,
    lp_codigo: Optional[str] = None,
    lp_descricao: Optional[str] = None,
    apenas_ativos: bool = True,
) -> list[MatchingManualFiscal]:
    query = (
        db.query(MatchingManualFiscal)
        .options(joinedload(MatchingManualFiscal.itens), joinedload(MatchingManualFiscal.usuario))
        .filter(MatchingManualFiscal.empresa_id == empresa_id)
    )
    if tipo:
        query = query.filter(MatchingManualFiscal.tipo == tipo)
    if periodo:
        query = query.filter(MatchingManualFiscal.periodo == periodo)
    if conta_contabil:
        query = query.filter(MatchingManualFiscal.conta_contabil == conta_contabil)
    if campo_imposto:
        query = query.filter(MatchingManualFiscal.campo_imposto == campo_imposto)
    if lp_codigo:
        query = query.filter(MatchingManualFiscal.lp_codigo == lp_codigo)
    if lp_descricao:
        query = query.filter(MatchingManualFiscal.lp_descricao == lp_descricao)
    if apenas_ativos:
        query = query.filter(MatchingManualFiscal.desfeito_em.is_(None))
    return query.order_by(MatchingManualFiscal.criado_em.desc()).all()


def desfazer(db: Session, matching_id: int, empresa_id: int, current_user: CurrentUser) -> MatchingManualFiscal:
    from datetime import datetime, timezone

    matching = (
        db.query(MatchingManualFiscal)
        .filter(MatchingManualFiscal.id == matching_id, MatchingManualFiscal.empresa_id == empresa_id)
        .first()
    )
    if not matching:
        raise HTTPException(404, "Matching manual nao encontrado")
    if matching.desfeito_em is not None:
        raise HTTPException(400, "Matching manual ja foi desfeito")

    matching.desfeito_em = datetime.now(timezone.utc)
    matching.desfeito_por_id = current_user.user_id
    db.commit()
    db.refresh(matching)

    logger.info("Matching manual %s desfeito por usuario=%s", matching_id, current_user.user_id)
    return matching


def aplicar_matches_manuais(
    razao_resultado: list[dict],
    sft_resultado: list[dict],
    matches: list[MatchingManualFiscal],
    campo_valor_ct2: str = "debito",
    campo_valor_sft: str = "valcont",
    tolerancia: float = TOLERANCIA_REAPLICACAO,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Marca como matched=True (mais a flag matched_manual) os itens de
    razao_resultado/sft_resultado que ainda estao sem correspondencia mas
    batem -- por historico+data+valor (CT2) e por filial+nf+cliefor+valor
    (SFT) -- com um matching manual ativo. Nao mexe em itens que ja vieram
    matched=True do algoritmo automatico.

    Retorna (razao_resultado, sft_resultado, matches_aplicados); o terceiro
    item lista, para cada matching manual que encontrou correspondencia nos
    dados atuais, quantos itens de cada lado foram de fato marcados -- usado
    pela tela pra diferenciar "casado manualmente" de "casado automatico".
    """
    ct2_indices_matched: set[int] = set()
    sft_indices_matched: set[int] = set()
    matches_aplicados: list[dict] = []

    for m in matches:
        itens_ct2 = [i for i in m.itens if i.lado == "ct2"]
        itens_sft = [i for i in m.itens if i.lado == "sft"]

        ct2_encontrados: list[int] = []
        for item in itens_ct2:
            for idx, rec in enumerate(razao_resultado):
                if idx in ct2_indices_matched or rec.get("matched"):
                    continue
                hist = str(rec.get("historico") or "").strip()
                data = str(rec.get("data") or "").strip()
                valor = round(float(rec.get(campo_valor_ct2) or 0), 2)
                if (
                    hist == (item.historico or "").strip()
                    and data == (item.data or "").strip()
                    and round(abs(valor - float(item.valor)), 2) <= tolerancia
                ):
                    ct2_indices_matched.add(idx)
                    ct2_encontrados.append(idx)
                    break

        sft_encontrados: list[int] = []
        for item in itens_sft:
            for idx, rec in enumerate(sft_resultado):
                if idx in sft_indices_matched or rec.get("matched"):
                    continue
                filial = str(rec.get("filial") or "").strip()
                nf = str(rec.get("nf") or "").strip()
                cliefor = str(rec.get("cliefor") or "").strip()
                valor = round(float(rec.get(campo_valor_sft) or 0), 2)
                if (
                    _norm_filial(filial) == _norm_filial(m.filial)
                    and _norm_nf(nf) == _norm_nf(m.nf)
                    and _norm_cliefor(cliefor) == _norm_cliefor(m.cliefor)
                    and round(abs(valor - float(item.valor)), 2) <= tolerancia
                ):
                    sft_indices_matched.add(idx)
                    sft_encontrados.append(idx)
                    break

        if ct2_encontrados or sft_encontrados:
            matches_aplicados.append({
                "matching_manual_id": m.id,
                "filial": m.filial,
                "nf": m.nf,
                "cliefor": m.cliefor,
                "qtd_ct2": len(ct2_encontrados),
                "qtd_sft": len(sft_encontrados),
            })

    for idx in ct2_indices_matched:
        razao_resultado[idx] = {**razao_resultado[idx], "matched": True, "matched_manual": True}
    for idx in sft_indices_matched:
        sft_resultado[idx] = {**sft_resultado[idx], "matched": True, "matched_manual": True}

    return razao_resultado, sft_resultado, matches_aplicados
