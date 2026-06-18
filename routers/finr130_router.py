from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

from sqlalchemy.orm import Session

from db import get_db
from services.finr130_service import FinR130Service, _titulos_para_registros
from services.protheus_carga_service import obter_registros_carga_concluida
from core.protheus import resolve_protheus_config
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id

router = APIRouter(prefix="/v1/finr130", tags=["FINR130"])
logger = logging.getLogger(__name__)


def _get_service(context: EmpresaContext, empresa_id: Optional[int], db: Session) -> FinR130Service:
    resolved_id = resolve_empresa_id(context, empresa_id)
    cfg = resolve_protheus_config(resolved_id, db)
    return FinR130Service(cfg.url, cfg.user, cfg.password, cfg.tenant, cfg.rest_prefix)


def _base_receber_params(
    data_base: str,
    cliente_de: Optional[str],
    cliente_ate: Optional[str],
    loja_de: Optional[str],
    loja_ate: Optional[str],
    prefixo_de: Optional[str],
    prefixo_ate: Optional[str],
    vencto_de: Optional[str],
    vencto_ate: Optional[str],
    natureza_de: Optional[str],
    natureza_ate: Optional[str],
    moeda: Optional[str],
    consid_filiais: Optional[str],
    filial_de: Optional[str],
    filial_ate: Optional[str],
    adiantamentos: Optional[str],
    abatimentos: Optional[str],
) -> dict:
    return {
        "data_base": data_base,
        "cliente_de": cliente_de, "cliente_ate": cliente_ate,
        "loja_de": loja_de, "loja_ate": loja_ate,
        "prefixo_de": prefixo_de, "prefixo_ate": prefixo_ate,
        "vencto_de": vencto_de, "vencto_ate": vencto_ate,
        "natureza_de": natureza_de, "natureza_ate": natureza_ate,
        "moeda": moeda,
        "consid_filiais": consid_filiais, "filial_de": filial_de, "filial_ate": filial_ate,
        "adiantamentos": adiantamentos, "abatimentos": abatimentos,
        "pageSize": 5000,
    }


def _cache_response_receber(registros_raw: list[dict], carga_id: int, page: Optional[int], page_size: int) -> dict:
    registros = _titulos_para_registros(registros_raw)

    if page is None:
        return {
            "registros": registros,
            "total": len(registros),
            "fonte": "cache_protheus",
            "carga_id": carga_id,
        }

    page = max(int(page), 1)
    page_size = max(int(page_size or 5000), 1)
    start = (page - 1) * page_size
    end = start + page_size
    total = len(registros)
    total_pages = max((total + page_size - 1) // page_size, 1)
    return {
        "parametros": {},
        "total_registros": total,
        "totalPages": total_pages,
        "page": page,
        "hasMore": page < total_pages,
        "registros": registros[start:end],
        "total": len(registros[start:end]),
        "fonte": "cache_protheus",
        "carga_id": carga_id,
    }


@router.get("")
async def get_titulos_receber(
    data_base: str = Query(..., description="Data base no formato YYYYMMDD"),
    page: Optional[int] = Query(None),
    pageSize: Optional[int] = Query(5000),
    cliente_de: Optional[str] = Query(None),
    cliente_ate: Optional[str] = Query(None),
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
    tit_descontados: Optional[str] = Query(None),
    saldo_retroativo: Optional[str] = Query(None),
    consid_filiais: Optional[str] = Query(None),
    filial_de: Optional[str] = Query(None),
    filial_ate: Optional[str] = Query(None),
    loja_de: Optional[str] = Query(None),
    loja_ate: Optional[str] = Query(None),
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
    considera_data: Optional[str] = Query(None),
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    """
    Proxy para o ZFINR130API do Protheus (Posicao dos Titulos a Receber).

    Quando page e informado, retorna somente aquela pagina do Protheus.
    Sem page, busca automaticamente todas as paginas e retorna o resultado consolidado.
    Configura PROTHEUS_URL no .env para nao precisar passar o parametro a cada chamada.
    """
    params = {
        "data_base": data_base,
        "page": page,
        "pageSize": pageSize,
        "cliente_de": cliente_de,
        "cliente_ate": cliente_ate,
        "prefixo_de": prefixo_de,
        "prefixo_ate": prefixo_ate,
        "num_de": num_de,
        "num_ate": num_ate,
        "banco_de": banco_de,
        "banco_ate": banco_ate,
        "vencto_de": vencto_de,
        "vencto_ate": vencto_ate,
        "natureza_de": natureza_de,
        "natureza_ate": natureza_ate,
        "emissao_de": emissao_de,
        "emissao_ate": emissao_ate,
        "moeda": moeda,
        "provisorios": provisorios,
        "reajuste_vencto": reajuste_vencto,
        "tit_descontados": tit_descontados,
        "saldo_retroativo": saldo_retroativo,
        "consid_filiais": consid_filiais,
        "filial_de": filial_de,
        "filial_ate": filial_ate,
        "loja_de": loja_de,
        "loja_ate": loja_ate,
        "adiantamentos": adiantamentos,
        "dtcontab_de": dtcontab_de,
        "dtcontab_ate": dtcontab_ate,
        "outras_moedas": outras_moedas,
        "tipos_incluir": tipos_incluir,
        "tipos_excluir": tipos_excluir,
        "abatimentos": abatimentos,
        "fluxo_caixa": fluxo_caixa,
        "comp_saldo_por": comp_saldo_por,
        "emissao_futura": emissao_futura,
        "taxa_moeda": taxa_moeda,
        "considera_data": considera_data,
    }

    service = _get_service(context, empresa_id, db)

    try:
        if page is not None:
            return await service.buscar_pagina(params)
        resultado = await service.buscar_todos_titulos(params)
        return resultado
    except Exception as exc:
        logger.exception("Erro ao consultar ZFINR130API")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.get(
    "/base-receber",
    summary="FINR130 formatado como base financeira de contas a receber",
    description=(
        "Retorna os titulos do FINR130 ja no formato de registros esperado pelo "
        "ProcessadorContasReceber, prontos para uso na conciliacao. "
        "Antes de consultar o Protheus, verifica se ja existe uma carga concluida "
        "com os mesmos parametros e reaproveita o cache."
    ),
)
async def get_como_base_receber(
    data_base: str = Query(..., description="Data base no formato YYYYMMDD"),
    page: Optional[int] = Query(None),
    pageSize: Optional[int] = Query(5000),
    cliente_de: Optional[str] = Query(None),
    cliente_ate: Optional[str] = Query(None),
    loja_de: Optional[str] = Query(None),
    loja_ate: Optional[str] = Query(None),
    prefixo_de: Optional[str] = Query(None),
    prefixo_ate: Optional[str] = Query(None),
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
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    params = _base_receber_params(
        data_base, cliente_de, cliente_ate, loja_de, loja_ate,
        prefixo_de, prefixo_ate,
        vencto_de, vencto_ate, natureza_de, natureza_ate, moeda,
        consid_filiais, filial_de, filial_ate, adiantamentos,
        abatimentos,
    )
    params["pageSize"] = pageSize or 5000
    if page is not None:
        params["page"] = page

    resolved_id = resolve_empresa_id(context, empresa_id)
    cache_carga, cache_registros_raw = obter_registros_carga_concluida(
        db,
        resolved_id,
        "FINR130",
        data_base,
        {k: v for k, v in params.items() if k != "page"},
    )
    if cache_carga:
        return _cache_response_receber(cache_registros_raw, cache_carga.id, page, params["pageSize"])

    service = _get_service(context, empresa_id, db)
    try:
        if page is not None:
            return await service.buscar_como_registros_pagina(params)
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar FINR130 como base_receber")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
