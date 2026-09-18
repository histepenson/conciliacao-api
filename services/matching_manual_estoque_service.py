"""
Service de Matching Manual de Estoque.

Cobre o caso em que o matching automatico
(tools/estoque/calc_diferencas_estoque.py) nao consegue casar um movimento
do Kardex (MATR900) com um lancamento do Razao Contabil de Estoque
(CTBR400) sozinho. Aqui o usuario confirma manualmente a correspondencia,
e essa decisao fica gravada -- reidentificada por chave de negocio (nao
por FK de linha, que ficaria orfa, ja que o Kardex/Razao sao reprocessados
do zero a cada "Processar Conciliacao") -- para ser reaplicada em cargas
futuras do mesmo periodo/conta.
"""

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from middleware.auth import CurrentUser
from models.matching_manual_estoque import MatchingManualEstoque, MatchingManualEstoqueItem
from schemas.matching_manual_estoque_schema import RequestCriarMatchingManualEstoque

logger = logging.getLogger(__name__)


def criar(
    db: Session,
    request: RequestCriarMatchingManualEstoque,
    current_user: CurrentUser,
) -> MatchingManualEstoque:
    if not request.itens_kardex:
        raise HTTPException(400, "Informe ao menos um movimento do Kardex (itens_kardex)")
    if not request.itens_razao:
        raise HTTPException(400, "Informe ao menos um lancamento do Razao (itens_razao)")

    valor_total_kardex = round(sum(float(r.get(request.campo_valor_kardex) or 0) for r in request.itens_kardex), 2)
    valor_total_razao = round(sum(float(r.get(request.campo_valor_razao) or 0) for r in request.itens_razao), 2)

    primeiro_kardex = request.itens_kardex[0]
    primeiro_razao = request.itens_razao[0]

    matching = MatchingManualEstoque(
        empresa_id=request.empresa_id,
        periodo=request.periodo,
        conta_contabil=request.conta_contabil,
        conta_contabil_id=request.conta_contabil_id,
        codigo_movimento=request.codigo_movimento,
        documento_numero=str(primeiro_kardex.get("documento_numero") or "")[:30] or None,
        codigo_produto=str(primeiro_kardex.get("codigo_produto") or "")[:30] or None,
        armazem=str(primeiro_kardex.get("armazem") or "")[:10] or None,
        data_kardex=str(primeiro_kardex.get("data") or "")[:10] or None,
        historico=str(primeiro_razao.get("historico") or "")[:200] or None,
        data_razao=str(primeiro_razao.get("data") or "")[:10] or None,
        valor_total_kardex=valor_total_kardex,
        valor_total_razao=valor_total_razao,
        observacao=request.observacao,
        usuario_id=current_user.user_id,
    )

    for rec in request.itens_kardex:
        matching.itens.append(MatchingManualEstoqueItem(
            lado="kardex",
            data=str(rec.get("data") or "")[:10] or None,
            documento_numero=str(rec.get("documento_numero") or "")[:30] or None,
            valor=round(float(rec.get(request.campo_valor_kardex) or 0), 2),
            dados_json=rec,
        ))
    for rec in request.itens_razao:
        matching.itens.append(MatchingManualEstoqueItem(
            lado="razao",
            data=str(rec.get("data") or "")[:10] or None,
            historico=str(rec.get("historico") or "")[:200] or None,
            valor=round(float(rec.get(request.campo_valor_razao) or 0), 2),
            dados_json=rec,
        ))

    db.add(matching)
    db.commit()
    db.refresh(matching)

    logger.info(
        "Matching manual estoque %s criado por usuario=%s empresa=%s periodo=%s conta=%s codigo_movimento=%s",
        matching.id, current_user.user_id, request.empresa_id, request.periodo,
        request.conta_contabil, request.codigo_movimento,
    )
    return matching


def listar(
    db: Session,
    empresa_id: int,
    periodo: Optional[str] = None,
    conta_contabil: Optional[str] = None,
    codigo_movimento: Optional[str] = None,
    apenas_ativos: bool = True,
) -> list[MatchingManualEstoque]:
    query = (
        db.query(MatchingManualEstoque)
        .options(joinedload(MatchingManualEstoque.itens), joinedload(MatchingManualEstoque.usuario))
        .filter(MatchingManualEstoque.empresa_id == empresa_id)
    )
    if periodo:
        query = query.filter(MatchingManualEstoque.periodo == periodo)
    if conta_contabil:
        query = query.filter(MatchingManualEstoque.conta_contabil == conta_contabil)
    if codigo_movimento:
        query = query.filter(MatchingManualEstoque.codigo_movimento == codigo_movimento)
    if apenas_ativos:
        query = query.filter(MatchingManualEstoque.desfeito_em.is_(None))
    return query.order_by(MatchingManualEstoque.criado_em.desc()).all()


def desfazer(db: Session, matching_id: int, empresa_id: int, current_user: CurrentUser) -> MatchingManualEstoque:
    from datetime import datetime, timezone

    matching = (
        db.query(MatchingManualEstoque)
        .filter(MatchingManualEstoque.id == matching_id, MatchingManualEstoque.empresa_id == empresa_id)
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

    logger.info("Matching manual estoque %s desfeito por usuario=%s", matching_id, current_user.user_id)
    return matching
