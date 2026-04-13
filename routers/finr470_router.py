from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from services.finr470_service import FinR470Service
from core.config import settings

router = APIRouter(prefix="/v1/finr470", tags=["FINR470"])
logger = logging.getLogger(__name__)


def _get_service(protheus_url: Optional[str]) -> FinR470Service:
    url = protheus_url or getattr(settings, "PROTHEUS_URL", None)
    if not url:
        raise HTTPException(
            status_code=422,
            detail=(
                "URL do Protheus nao configurada. "
                "Informe o parametro 'protheus_url' ou defina PROTHEUS_URL no .env"
            ),
        )
    user = getattr(settings, "PROTHEUS_USER", "")
    password = getattr(settings, "PROTHEUS_PASSWORD", "")
    tenant_id = getattr(settings, "PROTHEUS_TENANT", "02,0201")
    return FinR470Service(url, user, password, tenant_id)


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
    protheus_url: Optional[str] = Query(None),
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

    service = _get_service(protheus_url)
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
    protheus_url: Optional[str] = Query(None),
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

    service = _get_service(protheus_url)
    try:
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar FINR470 como base_extrato")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
