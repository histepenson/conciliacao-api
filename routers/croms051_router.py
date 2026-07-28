from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

from sqlalchemy.orm import Session

from db import get_db
from services.croms051_service import Croms051Service
from core.protheus import resolve_protheus_config
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id

router = APIRouter(prefix="/v1/croms051", tags=["CROMS051"])
logger = logging.getLogger(__name__)


def _get_service(context: EmpresaContext, empresa_id: Optional[int], db: Session) -> Croms051Service:
    resolved_id = resolve_empresa_id(context, empresa_id)
    cfg = resolve_protheus_config(resolved_id, db)
    return Croms051Service(cfg.url, cfg.user, cfg.password, cfg.tenant, cfg.rest_prefix)


@router.get(
    "",
    summary="Conta Corrente Desconto (CROMS051)",
    description=(
        "Proxy para o ZCROMS051API do Protheus. "
        "Busca automaticamente todas as paginas e retorna as linhas consolidadas."
    ),
)
async def get_conta_corrente_desconto(
    cliente: Optional[str] = Query(None, description="Codigo do cliente unico (default: todos)"),
    considera_data: Optional[str] = Query(None, description="1=Sim 2=Nao"),
    data_de: Optional[str] = Query(None, description="Data inicial - YYYYMMDD"),
    data_ate: Optional[str] = Query(None, description="Data final - YYYYMMDD"),
    modalidade_nova: Optional[str] = Query(None, description="1=Sim 2=Nao"),
    vendedor: Optional[str] = Query(None),
    filiais: Optional[str] = Query(None, description="Lista de filiais separadas por virgula"),
    pageSize: Optional[int] = Query(5000),
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    params = {
        "cliente": cliente,
        "considera_data": considera_data,
        "data_de": data_de,
        "data_ate": data_ate,
        "modalidade_nova": modalidade_nova,
        "vendedor": vendedor,
        "filiais": filiais,
        "pageSize": pageSize,
    }
    service = _get_service(context, empresa_id, db)
    try:
        return await service.buscar_extrato(params)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao consultar ZCROMS051API")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
