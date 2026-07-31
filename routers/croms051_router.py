from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging

from sqlalchemy.orm import Session

from db import get_db
from models.protheus_carga import ProtheusCargaRegistro
from services.croms051_service import Croms051Service
from services import protheus_carga_service
from services.estrategias.rancheiro.croms051_tratativas import (
    agrupar_croms051_por_cliente,
    aplicar_tratativas_croms051,
)
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


@router.get(
    "/carga/{carga_id}/resumo",
    summary="Resumo do CROMS051 agregado por cliente, a partir de uma carga concluida",
    description=(
        "Le os registros brutos (uma linha por transacao, ja com as tratativas de "
        "negocio aplicadas) de uma carga CROMS051 concluida, agrupa por cliente/loja "
        "somando valor e valor_associacao, e retorna somente esse resumo. "
        "Evita que o frontend precise baixar e reenviar centenas de milhares de "
        "linhas -- o abatimento por codigo depende apenas do total agregado por cliente."
    ),
)
def get_resumo_carga_croms051(
    carga_id: int,
    empresa_id: Optional[int] = Query(None, description="ID da empresa"),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    carga = protheus_carga_service.obter_carga(db, resolved_id, carga_id)

    if carga.tipo_relatorio.upper() != "CROMS051":
        raise HTTPException(status_code=400, detail="Carga informada nao e do tipo CROMS051")
    if carga.status != "concluido":
        raise HTTPException(status_code=409, detail=f"Carga ainda nao concluida (status={carga.status})")

    registros_raw = (
        db.query(ProtheusCargaRegistro)
        .filter(ProtheusCargaRegistro.carga_id == carga.id)
        .order_by(ProtheusCargaRegistro.sequencia)
        .all()
    )
    dados = [r.dados_json for r in registros_raw]

    # Os dados gravados na carga ja passaram por aplicar_tratativas_croms051
    # (ver Croms051Service.buscar_pagina/buscar_extrato), mas reaplicar aqui e'
    # idempotente e barato -- protege contra cargas antigas gravadas antes
    # dessa etapa existir.
    tratados = aplicar_tratativas_croms051(dados)
    agregados = agrupar_croms051_por_cliente(tratados)

    logger.info(
        "CROMS051 resumo -> carga_id=%s bruto=%s agregado_por_cliente=%s",
        carga.id, len(dados), len(agregados),
    )

    return {
        "carga_id": carga.id,
        "total_bruto": len(dados),
        "total_codigos": len(agregados),
        "registros": agregados,
    }
