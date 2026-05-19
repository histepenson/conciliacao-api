from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, timezone
import asyncio
import logging
import uuid

from sqlalchemy.orm import Session

from db import get_db
from services.finr150_service import FinR150Service
from core.protheus import resolve_protheus_config
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id

router = APIRouter(prefix="/v1/finr150", tags=["FINR150"])
logger = logging.getLogger(__name__)
_base_pagar_jobs: dict[str, dict] = {}


def _get_service(context: EmpresaContext, empresa_id: Optional[int], db: Session) -> FinR150Service:
    resolved_id = resolve_empresa_id(context, empresa_id)
    cfg = resolve_protheus_config(resolved_id, db)
    return FinR150Service(cfg.url, cfg.user, cfg.password, cfg.tenant, cfg.rest_prefix)


def _base_pagar_params(
    data_base: str,
    fornecedor_de: Optional[str],
    fornecedor_ate: Optional[str],
    loja_de: Optional[str],
    loja_ate: Optional[str],
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
    titulos_excluidos: Optional[str],
) -> dict:
    return {
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


async def _run_base_pagar_job(job_id: str, service: FinR150Service, params: dict) -> None:
    job = _base_pagar_jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        registros = await service.buscar_como_registros(params)
        job["status"] = "completed"
        job["registros"] = registros
        job["total"] = len(registros)
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.exception("Erro no job FINR150 base_pagar %s", job_id)
        job["status"] = "failed"
        job["error"] = f"Erro ao consultar Protheus: {exc}"
        job["completed_at"] = datetime.now(timezone.utc).isoformat()


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
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
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

    service = _get_service(context, empresa_id, db)
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
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    params = _base_pagar_params(
        data_base, fornecedor_de, fornecedor_ate, loja_de, loja_ate,
        vencto_de, vencto_ate, natureza_de, natureza_ate, moeda,
        consid_filiais, filial_de, filial_ate, adiantamentos,
        abatimentos, titulos_excluidos,
    )

    service = _get_service(context, empresa_id, db)
    try:
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar FINR150 como base_pagar")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.post(
    "/base-pagar/jobs",
    summary="Inicia job FINR150 formatado como base financeira de contas a pagar",
)
async def start_base_pagar_job(
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
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    params = _base_pagar_params(
        data_base, fornecedor_de, fornecedor_ate, loja_de, loja_ate,
        vencto_de, vencto_ate, natureza_de, natureza_ate, moeda,
        consid_filiais, filial_de, filial_ate, adiantamentos,
        abatimentos, titulos_excluidos,
    )
    service = _get_service(context, empresa_id, db)
    job_id = uuid.uuid4().hex
    _base_pagar_jobs[job_id] = {
        "status": "pending",
        "user_id": context.user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total": 0,
        "registros": [],
        "error": None,
    }
    asyncio.create_task(_run_base_pagar_job(job_id, service, params))
    return {"job_id": job_id, "status": "pending"}


@router.get(
    "/base-pagar/jobs/{job_id}",
    summary="Consulta status do job FINR150 base financeira de contas a pagar",
)
async def get_base_pagar_job(
    job_id: str,
    context: EmpresaContext = Depends(get_empresa_context),
):
    job = _base_pagar_jobs.get(job_id)
    if not job or job.get("user_id") != context.user_id:
        raise HTTPException(status_code=404, detail="Job nao encontrado")

    if job["status"] == "completed":
        return {
            "job_id": job_id,
            "status": job["status"],
            "registros": job["registros"],
            "total": job["total"],
        }

    if job["status"] == "failed":
        return {
            "job_id": job_id,
            "status": job["status"],
            "error": job.get("error") or "Erro ao consultar Protheus",
        }

    return {
        "job_id": job_id,
        "status": job["status"],
        "total": job["total"],
    }
