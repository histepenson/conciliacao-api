from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

from sqlalchemy.orm import Session

from db import get_db
from services.finr470_service import FinR470Service
from core.protheus import resolve_protheus_config
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id

router = APIRouter(prefix="/v1/finr470", tags=["FINR470"])
logger = logging.getLogger(__name__)


def _get_service(context: EmpresaContext, empresa_id: Optional[int], db: Session) -> FinR470Service:
    resolved_id = resolve_empresa_id(context, empresa_id)
    cfg = resolve_protheus_config(resolved_id, db)
    return FinR470Service(cfg.url, cfg.user, cfg.password, cfg.tenant, cfg.rest_prefix)


@router.get(
    "",
    summary="Extrato Bancario (FINR470)",
    description=(
        "Proxy para o ZFIN470API do Protheus. "
        "Busca automaticamente todas as paginas e retorna o extrato consolidado."
    ),
)
async def get_extrato(
    banco: str = Query(..., description="Banco"),
    agencia: str = Query(..., description="Agencia"),
    conta: str = Query(..., description="Conta"),
    data_ini: str = Query(..., description="Data inicial - YYYYMMDD"),
    data_fim: str = Query(..., description="Data final - YYYYMMDD"),
    moeda: Optional[str] = Query(None),
    situacao: Optional[str] = Query(None, description="1=Todos 2=Conciliados 3=Nao conciliados"),
    linhas_pagina: Optional[str] = Query(None),
    taxa_moeda: Optional[str] = Query(None),
    saldo_compart: Optional[str] = Query(None),
    todas_filiais: Optional[str] = Query(None),
    data_conv_saldo: Optional[str] = Query(None),
    pageSize: Optional[int] = Query(500),
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    params = {
        "banco": banco,
        "agencia": agencia,
        "conta": conta,
        "data_ini": data_ini,
        "data_fim": data_fim,
        "moeda": moeda,
        "situacao": situacao,
        "linhas_pagina": linhas_pagina,
        "taxa_moeda": taxa_moeda,
        "saldo_compart": saldo_compart,
        "todas_filiais": todas_filiais,
        "data_conv_saldo": data_conv_saldo,
        "pageSize": pageSize,
    }
    service = _get_service(context, empresa_id, db)
    try:
        return await service.buscar_extrato(params)
    except Exception as exc:
        logger.exception("Erro ao consultar ZFIN470API")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.get(
    "/base-extrato",
    summary="FINR470 formatado como base_extrato",
    description=(
        "Retorna os movimentos do FINR470 ja no formato de registros esperado pela conciliacao bancaria "
        "(`base_extrato.registros`), prontos para uso direto no backend/frontend."
    ),
)
async def get_como_base_extrato(
    banco: str = Query(...),
    agencia: str = Query(...),
    conta: str = Query(...),
    data_ini: str = Query(...),
    data_fim: str = Query(...),
    moeda: Optional[str] = Query(None),
    situacao: Optional[str] = Query(None),
    linhas_pagina: Optional[str] = Query(None),
    taxa_moeda: Optional[str] = Query(None),
    saldo_compart: Optional[str] = Query(None),
    todas_filiais: Optional[str] = Query(None),
    data_conv_saldo: Optional[str] = Query(None),
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    params = {
        "banco": banco,
        "agencia": agencia,
        "conta": conta,
        "data_ini": data_ini,
        "data_fim": data_fim,
        "moeda": moeda,
        "situacao": situacao,
        "linhas_pagina": linhas_pagina,
        "taxa_moeda": taxa_moeda,
        "saldo_compart": saldo_compart,
        "todas_filiais": todas_filiais,
        "data_conv_saldo": data_conv_saldo,
        "pageSize": 2000,
    }
    service = _get_service(context, empresa_id, db)
    try:
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar FINR470 como base_extrato")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
