"""
Router para Matching Manual Fiscal.

Cobre Conciliacao de Impostos e Pre-Conferencia: casos em que o CT2_KEY veio
vazio do Protheus e o matching automatico nao teve como desambiguar sozinho
entre mais de um fornecedor candidato na mesma NF/filial/data (ver
services/matching_manual_fiscal_service.py).

Endpoints:
- POST   /matching-manual-fiscal            - Cria um matching manual
- GET    /matching-manual-fiscal            - Lista matches (filtros por query)
- DELETE /matching-manual-fiscal/{id}       - Desfaz um matching manual
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.auth import CurrentUser, get_current_user
from schemas.matching_manual_fiscal_schema import MatchingManualFiscalOut, RequestCriarMatchingManual
from services import matching_manual_fiscal_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/matching-manual-fiscal",
    tags=["Matching Manual Fiscal"],
)


@router.post("/", response_model=MatchingManualFiscalOut, status_code=201)
def criar_matching_manual(
    request: RequestCriarMatchingManual,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return matching_manual_fiscal_service.criar(db, request, current_user)


@router.get("/", response_model=list[MatchingManualFiscalOut])
def listar_matching_manual(
    empresa_id: int = Query(...),
    tipo: str | None = Query(None, description="'impostos' ou 'pre_conferencia'"),
    periodo: str | None = Query(None, description="YYYY-MM"),
    conta_contabil: str | None = Query(None),
    campo_imposto: str | None = Query(None),
    lp_codigo: str | None = Query(None),
    lp_descricao: str | None = Query(None),
    apenas_ativos: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    matches = matching_manual_fiscal_service.listar(
        db, empresa_id=empresa_id, tipo=tipo, periodo=periodo,
        conta_contabil=conta_contabil, campo_imposto=campo_imposto,
        lp_codigo=lp_codigo, lp_descricao=lp_descricao, apenas_ativos=apenas_ativos,
    )
    return matches


@router.delete("/{matching_id}", response_model=MatchingManualFiscalOut)
def desfazer_matching_manual(
    matching_id: int,
    empresa_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    return matching_manual_fiscal_service.desfazer(db, matching_id, empresa_id, current_user)
