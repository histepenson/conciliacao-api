# routers/operacao_financeira_router.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.permission import Permissions, require_permission
from middleware.tenant import EmpresaContext, resolve_empresa_id
from schemas.operacao_financeira_schema import (
    OperacaoFinanceiraCreate,
    OperacaoFinanceiraResponse,
    OperacaoFinanceiraUpdate,
)
from services.operacao_financeira_service import (
    atualizar_operacao_financeira,
    buscar_operacao_financeira,
    criar_operacao_financeira,
    deletar_operacao_financeira,
    listar_operacoes_financeiras,
)

router = APIRouter(prefix="/operacao-financeira", tags=["Operacao Financeira"])


@router.get("", response_model=List[OperacaoFinanceiraResponse])
def route_listar_operacoes(
    empresa_id: Optional[int] = Query(None),
    modalidade: Optional[str] = Query(None, description="Filtra por modalidade, ex: LEASING"),
    ativo: Optional[bool] = Query(None, description="Filtra por ativo (Considera = Sim/Nao)"),
    skip: int = 0,
    limit: int = 1000,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.OPERACAO_FINANCEIRA_READ)),
):
    empresa_id_resolvido = resolve_empresa_id(context, empresa_id)
    return listar_operacoes_financeiras(db, empresa_id_resolvido, skip, limit, modalidade, ativo)


@router.get("/{id}", response_model=OperacaoFinanceiraResponse)
def route_buscar_operacao(
    id: int,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.OPERACAO_FINANCEIRA_READ)),
):
    operacao = buscar_operacao_financeira(db, id, context.empresa_id)
    if not operacao:
        raise HTTPException(status_code=404, detail="Operacao financeira nao encontrada")
    return operacao


@router.post("", response_model=OperacaoFinanceiraResponse, status_code=201)
def route_criar_operacao(
    operacao: OperacaoFinanceiraCreate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.OPERACAO_FINANCEIRA_WRITE)),
):
    dados = operacao.model_dump()
    dados["empresa_id"] = resolve_empresa_id(context, dados.get("empresa_id"))
    return criar_operacao_financeira(db, dados)


@router.put("/{id}", response_model=OperacaoFinanceiraResponse)
def route_atualizar_operacao(
    id: int,
    operacao: OperacaoFinanceiraUpdate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.OPERACAO_FINANCEIRA_WRITE)),
):
    updated = atualizar_operacao_financeira(db, id, operacao.model_dump(exclude_unset=True), context.empresa_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Operacao financeira nao encontrada")
    return updated


@router.delete("/{id}", status_code=204)
def route_deletar_operacao(
    id: int,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(require_permission(Permissions.OPERACAO_FINANCEIRA_WRITE)),
):
    sucesso = deletar_operacao_financeira(db, id, context.empresa_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Operacao financeira nao encontrada")
    return None
