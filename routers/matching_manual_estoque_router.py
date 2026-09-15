"""
Router para Matching Manual de Estoque.

Cobre a Conciliacao de Estoque (Kardex x Razao Contabil CTBR400): casos em
que o matching automatico nao consegue casar um movimento do Kardex com um
lancamento do Razao sozinho (ver
services/matching_manual_estoque_service.py).

Endpoints:
- POST   /matching-manual-estoque           - Cria um matching manual
- GET    /matching-manual-estoque           - Lista matches (filtros por query)
- DELETE /matching-manual-estoque/{id}      - Desfaz um matching manual
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.auth import CurrentUser, get_current_user
from schemas.matching_manual_estoque_schema import (
    MatchingManualEstoqueOut,
    RequestCriarMatchingManualEstoque,
)
from services import matching_manual_estoque_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/matching-manual-estoque",
    tags=["Matching Manual Estoque"],
)


@router.post("/", response_model=MatchingManualEstoqueOut, status_code=201)
def criar_matching_manual_estoque(
    request: RequestCriarMatchingManualEstoque,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return matching_manual_estoque_service.criar(db, request, current_user)


@router.get("/", response_model=list[MatchingManualEstoqueOut])
def listar_matching_manual_estoque(
    empresa_id: int = Query(...),
    periodo: str | None = Query(None, description="YYYY-MM"),
    conta_contabil: str | None = Query(None),
    codigo_movimento: str | None = Query(None),
    apenas_ativos: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    matches = matching_manual_estoque_service.listar(
        db, empresa_id=empresa_id, periodo=periodo,
        conta_contabil=conta_contabil, codigo_movimento=codigo_movimento,
        apenas_ativos=apenas_ativos,
    )
    return matches


@router.delete("/{matching_id}", response_model=MatchingManualEstoqueOut)
def desfazer_matching_manual_estoque(
    matching_id: int,
    empresa_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return matching_manual_estoque_service.desfazer(db, matching_id, empresa_id, current_user)
