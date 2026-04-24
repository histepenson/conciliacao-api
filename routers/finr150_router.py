from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import logging

from services.finr150_service import FinR150Service
from core.config import settings

router = APIRouter(prefix="/v1/finr150", tags=["FINR150"])
logger = logging.getLogger(__name__)


def _get_service(protheus_url: Optional[str]) -> FinR150Service:
    url = protheus_url or getattr(settings, "PROTHEUS_URL", None)
    if not url:
        raise HTTPException(
            status_code=422,
            detail="URL do Protheus nao configurada. Informe o parametro 'protheus_url' ou defina PROTHEUS_URL no .env",
        )
    user = getattr(settings, "PROTHEUS_USER", "")
    password = getattr(settings, "PROTHEUS_PASSWORD", "")
    tenant_id = getattr(settings, "PROTHEUS_TENANT", "02,0201")
    return FinR150Service(url, user, password, tenant_id)


@router.get("")
async def get_titulos_pagar(
    data_base: str = Query(..., description="Data base no formato YYYYMMDD"),
    page: Optional[int] = Query(None),
    pageSize: Optional[int] = Query(100),
    fornecedor_de: Optional[str] = Query(None),
    fornecedor_ate: Optional[str] = Query(None),
    loja_de: Optional[str] = Query(None),
    loja_ate: Optional[str] = Query(None),
    prefixo_de: Optional[str] = Query(None),
    prefixo_ate: Optional[str] = Query(None),
    num_de: Optional[str] = Query(None),
    num_ate: Optional[str] = Query(None),
    banco_de: Optional[str] = Query(None),
    banco_ate: Optional[str] = Query(None),
    vencto_de: Optional[str] = Query(None),
    vencto_ate: Optional[str] = Query(None),
    natureza_de: Optional[str] = Query(None),
    natureza_ate: Optional[str] = Query(None),
    emissao_de: Optional[str] = Query(None),
    emissao_ate: Optional[str] = Query(None),
    moeda: Optional[str] = Query(None),
    provisorios: Optional[str] = Query(None),
    reajuste_vencto: Optional[str] = Query(None),
    saldo_retroativo: Optional[str] = Query(None),
    consid_filiais: Optional[str] = Query(None),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    adiantamentos: Optional[str] = Query(None),
    dtcontab_de: Optional[str] = Query(None),
    dtcontab_ate: Optional[str] = Query(None),
    outras_moedas: Optional[str] = Query(None),
    tipos_incluir: Optional[str] = Query(None),
    tipos_excluir: Optional[str] = Query(None),
    abatimentos: Optional[str] = Query(None),
    fluxo_caixa: Optional[str] = Query(None),
    comp_saldo_por: Optional[str] = Query(None),
    emissao_futura: Optional[str] = Query(None),
    taxa_moeda: Optional[str] = Query(None),
    titulos_excluidos: Optional[str] = Query(None),
    protheus_url: Optional[str] = Query(None, description="URL base do servidor Protheus"),
):
    """
    Proxy para o ZFINR150API do Protheus (Posicao dos Titulos a Pagar).

    Busca automaticamente todas as paginas e retorna o resultado consolidado.
    """
    params = {
        "data_base": data_base, "page": page, "pageSize": pageSize,
        "fornecedor_de": fornecedor_de, "fornecedor_ate": fornecedor_ate,
        "loja_de": loja_de, "loja_ate": loja_ate,
        "prefixo_de": prefixo_de, "prefixo_ate": prefixo_ate,
        "num_de": num_de, "num_ate": num_ate,
        "banco_de": banco_de, "banco_ate": banco_ate,
        "vencto_de": vencto_de, "vencto_ate": vencto_ate,
        "natureza_de": natureza_de, "natureza_ate": natureza_ate,
        "emissao_de": emissao_de, "emissao_ate": emissao_ate,
        "moeda": moeda, "provisorios": provisorios,
        "reajuste_vencto": reajuste_vencto, "saldo_retroativo": saldo_retroativo,
        "consid_filiais": consid_filiais, "filial_de": filial_de, "filial_ate": filial_ate,
        "adiantamentos": adiantamentos,
        "dtcontab_de": dtcontab_de, "dtcontab_ate": dtcontab_ate,
        "outras_moedas": outras_moedas,
        "tipos_incluir": tipos_incluir, "tipos_excluir": tipos_excluir,
        "abatimentos": abatimentos, "fluxo_caixa": fluxo_caixa,
        "comp_saldo_por": comp_saldo_por, "emissao_futura": emissao_futura,
        "taxa_moeda": taxa_moeda, "titulos_excluidos": titulos_excluidos,
    }

    service = _get_service(protheus_url)
    try:
        return await service.buscar_todos_titulos(params)
    except Exception as exc:
        logger.exception("Erro ao consultar ZFINR150API")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.get(
    "/base-pagar",
    summary="FINR150 formatado como base financeira de contas a pagar",
    description=(
        "Retorna os titulos do FINR150 ja no formato de registros esperado pelo "
        "ProcessadorContasPagar, prontos para uso na conciliacao."
    ),
)
async def get_como_base_pagar(
    data_base: str = Query(..., description="Data base no formato YYYYMMDD"),
    fornecedor_de: Optional[str] = Query(None),
    fornecedor_ate: Optional[str] = Query(None),
    loja_de: Optional[str] = Query(None),
    loja_ate: Optional[str] = Query(None),
    vencto_de: Optional[str] = Query(None),
    vencto_ate: Optional[str] = Query(None),
    natureza_de: Optional[str] = Query(None),
    natureza_ate: Optional[str] = Query(None),
    moeda: Optional[str] = Query(None),
    consid_filiais: Optional[str] = Query(None),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    adiantamentos: Optional[str] = Query(None),
    abatimentos: Optional[str] = Query(None),
    titulos_excluidos: Optional[str] = Query(None),
    protheus_url: Optional[str] = Query(None),
):
    params = {
        "data_base": data_base,
        "fornecedor_de": fornecedor_de, "fornecedor_ate": fornecedor_ate,
        "loja_de": loja_de, "loja_ate": loja_ate,
        "vencto_de": vencto_de, "vencto_ate": vencto_ate,
        "natureza_de": natureza_de, "natureza_ate": natureza_ate,
        "moeda": moeda,
        "consid_filiais": consid_filiais, "filial_de": filial_de, "filial_ate": filial_ate,
        "adiantamentos": adiantamentos, "abatimentos": abatimentos,
        "titulos_excluidos": titulos_excluidos,
        "pageSize": 500,
    }

    service = _get_service(protheus_url)
    try:
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar FINR150 como base_pagar")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
