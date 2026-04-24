from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from services.ctbr480_service import Ctbr480Service
from core.config import settings

router = APIRouter(prefix="/v1/ctbr480", tags=["CTBR480"])
logger = logging.getLogger(__name__)


def _get_service(protheus_url: Optional[str]) -> Ctbr480Service:
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
    return Ctbr480Service(url, user, password, tenant_id)


@router.get(
    "",
    summary="Razao Contabil por Item (CTBR480)",
    description=(
        "Proxy para o ZCTBR480API do Protheus. "
        "Busca automaticamente todas as paginas e retorna o razao contabil consolidado."
    ),
)
async def get_razao(
    data_fim: str = Query(..., description="Data fim do periodo -- YYYYMMDD"),
    data_ini: Optional[str] = Query(None, description="Data inicio -- YYYYMMDD (default: 01/01 do ano de data_fim)"),
    page: Optional[int] = Query(None),
    pageSize: Optional[int] = Query(500),
    item_de: Optional[str] = Query(None, description="Item contabil inicial (CTD_ITEM)  (par01)"),
    item_ate: Optional[str] = Query(None, description="Item contabil final               (par02)"),
    conta_de: Optional[str] = Query(None, description="Conta contabil inicial (CT1_CONTA)(par12)"),
    conta_ate: Optional[str] = Query(None, description="Conta contabil final              (par13)"),
    custo_de: Optional[str] = Query(None, description="Centro de custo inicial (CTT)      (par15)"),
    custo_ate: Optional[str] = Query(None, description="Centro de custo final             (par16)"),
    clvl_de: Optional[str] = Query(None, description="Classe de valor inicial (CTH)       (par18)"),
    clvl_ate: Optional[str] = Query(None, description="Classe de valor final              (par19)"),
    moeda: Optional[str] = Query(None, description="Moeda (default: 1)                   (par05)"),
    saldo: Optional[str] = Query(None, description="Tipo de saldo CQ5_TPSALD (default: 1)(par06)"),
    set_of_books: Optional[str] = Query(None, description="Set of Books                  (par07)"),
    vlr_zerado: Optional[str] = Query(None, description="1=Inclui zeros  2=Exclui        (par27)"),
    consid_filiais: Optional[str] = Query(None, description="1=Range  2=Filial corrente   (par29)"),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    protheus_url: Optional[str] = Query(None, description="URL base do Protheus (ex: https://192.168.1.100:8089)"),
):
    """
    Retorna o razao contabil bruto do CTBR480 com campos:
    `data`, `lote_sub_doc_linha`, `historico`, `xpartida`, `c_custo`,
    `item_conta`, `cod_cl_val`, `debito`, `credito`, `saldo_atual`,
    `conta`, `desc_item`, `desc_conta`, `normal_item`, `normal_cta`.
    """
    params = {
        "data_fim": data_fim,
        "data_ini": data_ini,
        "page": page,
        "pageSize": pageSize,
        "item_de": item_de,
        "item_ate": item_ate,
        "conta_de": conta_de,
        "conta_ate": conta_ate,
        "custo_de": custo_de,
        "custo_ate": custo_ate,
        "clvl_de": clvl_de,
        "clvl_ate": clvl_ate,
        "moeda": moeda,
        "saldo": saldo,
        "set_of_books": set_of_books,
        "vlr_zerado": vlr_zerado,
        "consid_filiais": consid_filiais,
        "filial_de": filial_de,
        "filial_ate": filial_ate,
    }

    service = _get_service(protheus_url)
    try:
        return await service.buscar_razao(params)
    except Exception as exc:
        logger.exception("Erro ao consultar ZCTBR480API")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.get(
    "/base-contabil-geral",
    summary="CTBR480 formatado como base_contabil_geral",
    description=(
        "Retorna os lancamentos do CTBR480 ja no formato de registros esperado pela conciliacao "
        "(`base_contabil_geral.registros`), prontos para uso direto sem upload de arquivo."
    ),
)
async def get_como_base_contabil_geral(
    data_fim: str = Query(..., description="Data fim do periodo -- YYYYMMDD"),
    data_ini: Optional[str] = Query(None),
    item_de: Optional[str] = Query(None),
    item_ate: Optional[str] = Query(None),
    conta_de: Optional[str] = Query(None),
    conta_ate: Optional[str] = Query(None),
    custo_de: Optional[str] = Query(None),
    custo_ate: Optional[str] = Query(None),
    clvl_de: Optional[str] = Query(None),
    clvl_ate: Optional[str] = Query(None),
    moeda: Optional[str] = Query(None),
    saldo: Optional[str] = Query(None),
    vlr_zerado: Optional[str] = Query(None),
    consid_filiais: Optional[str] = Query(None),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    protheus_url: Optional[str] = Query(None),
):
    """
    Cada registro retornado tem os mesmos campos do Excel CTBR480:
    `data`, `lote_sub_doc_linha`, `historico`, `xpartida`, `c_custo`,
    `item_conta`, `cod_cl_val`, `debito`, `credito`, `saldo_atual`.

    Compativel diretamente com `analise_diferencas_service.py` que ja normaliza
    esses nomes de colunas ao processar o razao geral.
    """
    params = {
        "data_fim": data_fim,
        "data_ini": data_ini,
        "item_de": item_de,
        "item_ate": item_ate,
        "conta_de": conta_de,
        "conta_ate": conta_ate,
        "custo_de": custo_de,
        "custo_ate": custo_ate,
        "clvl_de": clvl_de,
        "clvl_ate": clvl_ate,
        "moeda": moeda,
        "saldo": saldo,
        "vlr_zerado": vlr_zerado,
        "consid_filiais": consid_filiais,
        "filial_de": filial_de,
        "filial_ate": filial_ate,
        "pageSize": 2000,  # traz tudo em uma unica chamada ao Protheus
    }

    service = _get_service(protheus_url)
    try:
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar CTBR480 como base contabil geral")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
