from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from services.ctbr400_service import Ctbr400Service
from core.config import settings

router = APIRouter(prefix="/v1/ctbr400", tags=["CTBR400"])
logger = logging.getLogger(__name__)


def _get_service(protheus_url: Optional[str]) -> Ctbr400Service:
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
    return Ctbr400Service(url, user, password, tenant_id)


@router.get(
    "",
    summary="Razao Contabil (CTBR400)",
    description=(
        "Proxy para o ZCTBR400API do Protheus. "
        "Busca automaticamente todas as paginas e retorna o razao contabil consolidado."
    ),
)
async def get_razao(
    data_fim: str = Query(..., description="Data fim do periodo - YYYYMMDD"),
    data_ini: Optional[str] = Query(None, description="Data inicio - YYYYMMDD"),
    pageSize: Optional[int] = Query(500),
    conta_de: Optional[str] = Query(None),
    conta_ate: Optional[str] = Query(None),
    custo_de: Optional[str] = Query(None),
    custo_ate: Optional[str] = Query(None),
    item_de: Optional[str] = Query(None),
    item_ate: Optional[str] = Query(None),
    clvl_de: Optional[str] = Query(None),
    clvl_ate: Optional[str] = Query(None),
    moeda: Optional[str] = Query("01"),
    saldo: Optional[str] = Query("1"),
    set_of_books: Optional[str] = Query(None),
    imprime_custo: Optional[str] = Query("2"),
    imprime_item: Optional[str] = Query("2"),
    imprime_clvl: Optional[str] = Query("2"),
    tipo_rel: Optional[str] = Query("1", description="1=Analitico 2=Resumido 3=Sintetico"),
    salta_linha: Optional[str] = Query("1"),
    moeda_desc: Optional[str] = Query(None),
    consid_filiais: Optional[str] = Query("2"),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    protheus_url: Optional[str] = Query(None),
):
    params = {
        "data_fim": data_fim,
        "data_ini": data_ini,
        "pageSize": pageSize,
        "conta_de": conta_de,
        "conta_ate": conta_ate,
        "custo_de": custo_de,
        "custo_ate": custo_ate,
        "item_de": item_de,
        "item_ate": item_ate,
        "clvl_de": clvl_de,
        "clvl_ate": clvl_ate,
        "moeda": moeda,
        "saldo": saldo,
        "set_of_books": set_of_books,
        "imprime_custo": imprime_custo,
        "imprime_item": imprime_item,
        "imprime_clvl": imprime_clvl,
        "tipo_rel": tipo_rel,
        "salta_linha": salta_linha,
        "moeda_desc": moeda_desc,
        "consid_filiais": consid_filiais,
        "filial_de": filial_de,
        "filial_ate": filial_ate,
    }

    service = _get_service(protheus_url)
    try:
        return await service.buscar_razao(params)
    except Exception as exc:
        logger.exception("Erro ao consultar ZCTBR400API")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.get(
    "/base-razao",
    summary="CTBR400 formatado como base_razao",
    description=(
        "Retorna os lancamentos do CTBR400 no mesmo formato de registros usado hoje "
        "pelos normalizadores do backend, eliminando o upload do Excel."
    ),
)
async def get_como_base_razao(
    data_fim: str = Query(...),
    data_ini: Optional[str] = Query(None),
    conta_de: Optional[str] = Query(None),
    conta_ate: Optional[str] = Query(None),
    custo_de: Optional[str] = Query(None),
    custo_ate: Optional[str] = Query(None),
    item_de: Optional[str] = Query(None),
    item_ate: Optional[str] = Query(None),
    clvl_de: Optional[str] = Query(None),
    clvl_ate: Optional[str] = Query(None),
    moeda: Optional[str] = Query("01"),
    saldo: Optional[str] = Query("1"),
    set_of_books: Optional[str] = Query(None),
    imprime_custo: Optional[str] = Query("2"),
    imprime_item: Optional[str] = Query("2"),
    imprime_clvl: Optional[str] = Query("2"),
    tipo_rel: Optional[str] = Query("1"),
    salta_linha: Optional[str] = Query("1"),
    moeda_desc: Optional[str] = Query(None),
    consid_filiais: Optional[str] = Query("2"),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    protheus_url: Optional[str] = Query(None),
):
    params = {
        "data_fim": data_fim,
        "data_ini": data_ini,
        "conta_de": conta_de,
        "conta_ate": conta_ate,
        "custo_de": custo_de,
        "custo_ate": custo_ate,
        "item_de": item_de,
        "item_ate": item_ate,
        "clvl_de": clvl_de,
        "clvl_ate": clvl_ate,
        "moeda": moeda,
        "saldo": saldo,
        "set_of_books": set_of_books,
        "imprime_custo": imprime_custo,
        "imprime_item": imprime_item,
        "imprime_clvl": imprime_clvl,
        "tipo_rel": tipo_rel,
        "salta_linha": salta_linha,
        "moeda_desc": moeda_desc,
        "consid_filiais": consid_filiais,
        "filial_de": filial_de,
        "filial_ate": filial_ate,
        "pageSize": 2000,
    }

    service = _get_service(protheus_url)
    try:
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar CTBR400 como base_razao")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
