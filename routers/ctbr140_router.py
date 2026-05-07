from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

from sqlalchemy.orm import Session

from db import get_db
from services.ctbr140_service import Ctbr140Service
from core.config import settings
from core.protheus import resolve_protheus_tenant

router = APIRouter(prefix="/v1/ctbr140", tags=["CTBR140"])
logger = logging.getLogger(__name__)


def _get_service(protheus_url: Optional[str], tenant_id: str) -> Ctbr140Service:
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
    return Ctbr140Service(url, user, password, tenant_id)


@router.get(
    "",
    summary="Balancete de Conta/Item (CTBR140)",
    description=(
        "Proxy para o ZCTBR140API do Protheus. "
        "Busca automaticamente todas as paginas e retorna o balancete consolidado."
    ),
)
async def get_balancete(
    data_fim: str = Query(..., description="Data fim do periodo -- YYYYMMDD"),
    data_ini: Optional[str] = Query(None, description="Data inicio -- YYYYMMDD (default: 01/01 do ano de data_fim)"),
    page: Optional[int] = Query(None),
    pageSize: Optional[int] = Query(200),
    conta_de: Optional[str] = Query(None, description="Conta contabil inicial (CT1_CONTA)"),
    conta_ate: Optional[str] = Query(None, description="Conta contabil final"),
    item_de: Optional[str] = Query(None, description="Item/CC inicial (CTD_ITEM)"),
    item_ate: Optional[str] = Query(None, description="Item/CC final"),
    tipo_balancete: Optional[str] = Query(None, description="1=Analitico  2=Sintetico  3=Ambos"),
    set_of_books: Optional[str] = Query(None),
    vlr_zerado: Optional[str] = Query(None, description="1=Inclui zeros  2=Exclui (default: 2)"),
    moeda: Optional[str] = Query(None, description="Moeda (default: 1)"),
    tp_lanc: Optional[str] = Query(None, description="Tipo de lancamento (vazio = todos)"),
    imp_mov: Optional[str] = Query(None, description="1=Retorna coluna movimento  2=Nao (default: 1)"),
    divide_por: Optional[str] = Query(None, description="1=Nenhum  2=/100  3=/1000  4=/1M"),
    sld_ant_lp: Optional[str] = Query(None, description="1=Usa data_lp para saldo anterior  2=Usa data_ini-1"),
    data_lp: Optional[str] = Query(None, description="Data base LP para saldo anterior -- YYYYMMDD"),
    consid_filiais: Optional[str] = Query(None, description="1=Range de filiais  2=Filial corrente (default: 2)"),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    protheus_url: Optional[str] = Query(None, description="URL base do Protheus (ex: https://192.168.1.100:8089)"),
    empresa_id: Optional[int] = Query(None, description="ID da empresa para resolver o Tenant ID do Protheus"),
    db: Session = Depends(get_db),
):
    """
    Retorna o balancete bruto do CTBR140 com campos:
    `conta`, `item`, `desc_conta`, `desc_item`, `normal_cta`, `saldo_ant`, `debito`, `credito`, `saldo_atu`.
    """
    params = {
        "data_fim": data_fim,
        "data_ini": data_ini,
        "page": page,
        "pageSize": pageSize,
        "conta_de": conta_de,
        "conta_ate": conta_ate,
        "item_de": item_de,
        "item_ate": item_ate,
        "tipo_balancete": tipo_balancete,
        "set_of_books": set_of_books,
        "vlr_zerado": vlr_zerado,
        "moeda": moeda,
        "tp_lanc": tp_lanc,
        "imp_mov": imp_mov,
        "divide_por": divide_por,
        "sld_ant_lp": sld_ant_lp,
        "data_lp": data_lp,
        "consid_filiais": consid_filiais,
        "filial_de": filial_de,
        "filial_ate": filial_ate,
    }

    tenant_id = resolve_protheus_tenant(empresa_id, db)
    service = _get_service(protheus_url, tenant_id)
    try:
        return await service.buscar_balancete(params)
    except Exception as exc:
        logger.exception("Erro ao consultar ZCTBR140API")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.get(
    "/base-contabil",
    summary="CTBR140 formatado como base_contabil_filtrada",
    description=(
        "Retorna os dados do CTBR140 ja no formato de registros esperado pela conciliacao "
        "(`base_contabil_filtrada.registros`), prontos para uso direto sem upload de arquivo."
    ),
)
async def get_como_base_contabil(
    data_fim: str = Query(..., description="Data fim do periodo -- YYYYMMDD"),
    data_ini: Optional[str] = Query(None),
    conta_de: Optional[str] = Query(None),
    conta_ate: Optional[str] = Query(None),
    item_de: Optional[str] = Query(None),
    item_ate: Optional[str] = Query(None),
    tipo_balancete: Optional[str] = Query(None, description="1=Analitico  2=Sintetico  3=Ambos  (par07)"),
    vlr_zerado: Optional[str] = Query(None, description="1=Incluir zeros  2=Excluir  (par09)"),
    moeda: Optional[str] = Query(None, description="Moeda (par10)"),
    tp_lanc: Optional[str] = Query(None, description="Tipo de saldo CQ5_TPSALD (par12)"),
    imp_mov: Optional[str] = Query(None, description="1=Imprime coluna movimento  2=Nao  (par18)"),
    divide_por: Optional[str] = Query(None, description="1=Nenhum  2=/100  3=/1000  4=/1M  (par24)"),
    sld_ant_lp: Optional[str] = Query(None, description="1=Usa data_lp  2=Usa data_ini-1  (par26)"),
    data_lp: Optional[str] = Query(None, description="Data base LP -- YYYYMMDD  (par27)"),
    consid_filiais: Optional[str] = Query(None, description="1=Range de filiais  2=Filial corrente  (par28)"),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    protheus_url: Optional[str] = Query(None),
    empresa_id: Optional[int] = Query(None, description="ID da empresa para resolver o Tenant ID do Protheus"),
    db: Session = Depends(get_db),
):
    """
    Cada registro retornado tem o formato:
    `{"Codigo": "<CTD_ITEM>", "Descricao": "<desc_item>", "Saldo atual": <float>}`

    Parametros mapeados 1:1 com as perguntas do relatorio CTBR140 (CTR140).
    O valor de "Saldo atual" ja esta ajustado pela direcao normal da conta:
    - Debito-normal (normal_cta=1): saldo_atu direto
    - Credito-normal (normal_cta=2): -saldo_atu (invertido para positivo)
    """
    params = {
        "data_fim": data_fim,
        "data_ini": data_ini,
        "conta_de": conta_de,
        "conta_ate": conta_ate,
        "item_de": item_de,
        "item_ate": item_ate,
        "tipo_balancete": tipo_balancete,
        "vlr_zerado": vlr_zerado,
        "moeda": moeda,
        "tp_lanc": tp_lanc,
        "imp_mov": imp_mov,
        "divide_por": divide_por,
        "sld_ant_lp": sld_ant_lp,
        "data_lp": data_lp,
        "consid_filiais": consid_filiais,
        "filial_de": filial_de,
        "filial_ate": filial_ate,
    }

    tenant_id = resolve_protheus_tenant(empresa_id, db)
    service = _get_service(protheus_url, tenant_id)
    try:
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar CTBR140 como base contabil")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
