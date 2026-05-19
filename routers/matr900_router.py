from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

from sqlalchemy.orm import Session

from db import get_db
from services.matr900_service import Matr900Service
from core.protheus import resolve_protheus_config
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id

router = APIRouter(prefix="/v1/matr900", tags=["MATR900"])
logger = logging.getLogger(__name__)


def _get_service(context: EmpresaContext, empresa_id: Optional[int], db: Session) -> Matr900Service:
    resolved_id = resolve_empresa_id(context, empresa_id)
    cfg = resolve_protheus_config(resolved_id, db)
    return Matr900Service(cfg.url, cfg.user, cfg.password, cfg.tenant, cfg.rest_prefix)


@router.get(
    "",
    summary="Kardex Fisico-Financeiro (MATR900)",
    description=(
        "Proxy para o ZMATR900API do Protheus. "
        "Busca automaticamente todas as paginas e retorna o Kardex consolidado."
    ),
)
async def get_kardex(
    data_ini: str = Query(..., description="Data inicio do periodo - YYYYMMDD"),
    data_fim: str = Query(..., description="Data fim do periodo - YYYYMMDD"),
    pageSize: Optional[int] = Query(500),
    produto_de: Optional[str] = Query(None),
    produto_ate: Optional[str] = Query(None),
    tipo_de: Optional[str] = Query(None),
    tipo_ate: Optional[str] = Query(None),
    grupo_de: Optional[str] = Query(None),
    grupo_ate: Optional[str] = Query(None),
    armazem: Optional[str] = Query(None),
    documento_por: Optional[str] = Query("D", description="D=Documento S=Sequencia"),
    moeda: Optional[str] = Query("1"),
    ordem: Optional[str] = Query("1", description="1=Produto 2=Tipo"),
    lista_sem_movimento: Optional[str] = Query("2"),
    lista_transferencia: Optional[str] = Query("1"),
    considera_filiais: Optional[str] = Query("2"),
    tipo_custo: Optional[str] = Query("1", description="1=Medio 2=Reposicao"),
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    params = {
        "data_ini": data_ini,
        "data_fim": data_fim,
        "pageSize": pageSize,
        "produto_de": produto_de,
        "produto_ate": produto_ate,
        "tipo_de": tipo_de,
        "tipo_ate": tipo_ate,
        "grupo_de": grupo_de,
        "grupo_ate": grupo_ate,
        "armazem": armazem,
        "documento_por": documento_por,
        "moeda": moeda,
        "ordem": ordem,
        "lista_sem_movimento": lista_sem_movimento,
        "lista_transferencia": lista_transferencia,
        "considera_filiais": considera_filiais,
        "tipo_custo": tipo_custo,
    }

    service = _get_service(context, empresa_id, db)
    try:
        return await service.buscar_kardex(params)
    except Exception as exc:
        logger.exception("Erro ao consultar ZMATR900API")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")


@router.get(
    "/base-kardex",
    summary="MATR900 formatado como base_kardex",
    description=(
        "Retorna os movimentos do Kardex no mesmo formato de registros usado hoje "
        "pelo normalizador do backend, eliminando o upload do Excel."
    ),
)
async def get_como_base_kardex(
    data_ini: str = Query(...),
    data_fim: str = Query(...),
    produto_de: Optional[str] = Query(None),
    produto_ate: Optional[str] = Query(None),
    tipo_de: Optional[str] = Query(None),
    tipo_ate: Optional[str] = Query(None),
    grupo_de: Optional[str] = Query(None),
    grupo_ate: Optional[str] = Query(None),
    armazem: Optional[str] = Query(None),
    documento_por: Optional[str] = Query("D"),
    moeda: Optional[str] = Query("1"),
    ordem: Optional[str] = Query("1"),
    lista_sem_movimento: Optional[str] = Query("2"),
    lista_transferencia: Optional[str] = Query("1"),
    considera_filiais: Optional[str] = Query("2"),
    tipo_custo: Optional[str] = Query("1"),
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    context: EmpresaContext = Depends(get_empresa_context),
    db: Session = Depends(get_db),
):
    params = {
        "data_ini": data_ini,
        "data_fim": data_fim,
        "produto_de": produto_de,
        "produto_ate": produto_ate,
        "tipo_de": tipo_de,
        "tipo_ate": tipo_ate,
        "grupo_de": grupo_de,
        "grupo_ate": grupo_ate,
        "armazem": armazem,
        "documento_por": documento_por,
        "moeda": moeda,
        "ordem": ordem,
        "lista_sem_movimento": lista_sem_movimento,
        "lista_transferencia": lista_transferencia,
        "considera_filiais": considera_filiais,
        "tipo_custo": tipo_custo,
        "pageSize": 2000,
    }

    service = _get_service(context, empresa_id, db)
    try:
        registros = await service.buscar_como_registros(params)
        return {"registros": registros, "total": len(registros)}
    except Exception as exc:
        logger.exception("Erro ao buscar MATR900 como base_kardex")
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Protheus: {exc}")
