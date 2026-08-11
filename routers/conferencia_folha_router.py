import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.particularidades import ChaveParticularidade
from core.protheus import resolve_protheus_config
from db import get_db
from middleware.empresa_config import require_configuracao
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id
from schemas.conferencia_folha_schema import (
    ContasConferenciaFolhaResponse,
    ExecutarContaFolhaRequest,
    ResultadoContaFolha,
)
from services.conferencia_folha_service import (
    ConferenciaFolhaService,
    ContaFolhaNaoConfiguradaError,
    listar_contas_configuradas,
)
from services.ctbr480_service import Ctbr480Service
from services.folha_pagamento_service import FolhaPagamentoService

router = APIRouter(
    prefix="/v1/conferencia-folha",
    tags=["Conferencia Folha"],
    dependencies=[Depends(require_configuracao(ChaveParticularidade.TEM_CONFERENCIA_FOLHA))],
)
logger = logging.getLogger(__name__)


def _get_motor(context: EmpresaContext, empresa_id: Optional[int], db: Session) -> ConferenciaFolhaService:
    resolved_id = resolve_empresa_id(context, empresa_id)
    cfg = resolve_protheus_config(resolved_id, db)
    folha_service = FolhaPagamentoService(cfg.url, cfg.user, cfg.password, cfg.tenant, cfg.rest_prefix)
    razao_service = Ctbr480Service(cfg.url, cfg.user, cfg.password, cfg.tenant, cfg.rest_prefix)
    return ConferenciaFolhaService(folha_service, razao_service)


@router.get(
    "/contas",
    response_model=ContasConferenciaFolhaResponse,
    summary="Lista contas vinculadas a uma situacao de Conferencia Folha",
)
def get_contas(
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return ContasConferenciaFolhaResponse(contas=listar_contas_configuradas(db, resolved_id))


@router.post(
    "/contas/{conta_id}/executar",
    response_model=ResultadoContaFolha,
    summary="Processa a Conferencia Folha de uma conta (filtros manuais da situacao + periodo)",
)
async def post_executar_conta(
    conta_id: int,
    request: ExecutarContaFolhaRequest,
    empresa_id: Optional[int] = Query(None),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    motor = _get_motor(context, empresa_id, db)
    try:
        return await motor.executar_conta(db, resolved_id, conta_id, request.periodo, request.filtros)
    except ContaFolhaNaoConfiguradaError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao executar Conferencia Folha para conta %s", conta_id)
        raise HTTPException(status_code=502, detail=f"Erro ao processar: {exc}")
