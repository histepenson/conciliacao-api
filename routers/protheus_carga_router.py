from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id
from schemas.protheus_carga_schema import (
    ProtheusCargaConfigCreate,
    ProtheusCargaConfigOut,
    ProtheusCargaConfigUpdate,
    ProtheusCargaCreate,
    ProtheusCargaEnfileirada,
    ProtheusCargaOut,
    ProtheusCargaRegistrosPage,
)
from services import protheus_carga_service as service

router = APIRouter(prefix="/v1/protheus-cargas", tags=["Protheus Cargas"])


@router.get("/configs", response_model=list[ProtheusCargaConfigOut])
def get_configs(
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return service.listar_configs(db, resolved_id)


@router.post("/configs", response_model=ProtheusCargaConfigOut)
def post_config(
    payload: ProtheusCargaConfigCreate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, payload.empresa_id)
    return service.criar_config(db, resolved_id, payload)


@router.patch("/configs/{config_id}", response_model=ProtheusCargaConfigOut)
def patch_config(
    config_id: int,
    payload: ProtheusCargaConfigUpdate,
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return service.atualizar_config(db, resolved_id, config_id, payload)


@router.post("/configs/{config_id}/executar", response_model=ProtheusCargaEnfileirada)
def executar_config(
    config_id: int,
    empresa_id: Optional[int] = Query(None),
    data_base: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    carga, reutilizavel = service.enfileirar_config(db, resolved_id, config_id, data_base=data_base)
    return {
        "carga": carga,
        "reutilizavel": reutilizavel,
        "mensagem": _mensagem_enfileiramento(carga.status, reutilizavel),
    }


@router.get("", response_model=list[ProtheusCargaOut])
def get_cargas(
    empresa_id: Optional[int] = Query(None),
    tipo_relatorio: Optional[str] = Query(None),
    data_base: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return service.listar_cargas(db, resolved_id, tipo_relatorio, data_base, status, limit)


@router.post("", response_model=ProtheusCargaEnfileirada)
def post_carga(
    payload: ProtheusCargaCreate,
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, payload.empresa_id)
    carga, reutilizavel = service.criar_ou_enfileirar_carga(db, resolved_id, payload)
    return {
        "carga": carga,
        "reutilizavel": reutilizavel,
        "mensagem": _mensagem_enfileiramento(carga.status, reutilizavel),
    }


@router.post("/agendar-diario", response_model=list[ProtheusCargaEnfileirada])
def agendar_diario(
    empresa_id: Optional[int] = Query(None),
    data_base: str = Query(..., min_length=8, max_length=8),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    configs = service.listar_configs(db, resolved_id)
    retorno = []
    for config in configs:
        if not config.ativo or not config.atualizar_automatico:
            continue
        carga, reutilizavel = service.enfileirar_config(db, resolved_id, config.id, data_base=data_base)
        retorno.append(
            {
                "carga": carga,
                "reutilizavel": reutilizavel,
                "mensagem": _mensagem_enfileiramento(carga.status, reutilizavel),
            }
        )
    return retorno


@router.get("/{carga_id}", response_model=ProtheusCargaOut)
def get_carga(
    carga_id: int,
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return service.obter_carga(db, resolved_id, carga_id)


@router.post("/{carga_id}/reprocessar", response_model=ProtheusCargaOut)
def reprocessar(
    carga_id: int,
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    return service.reprocessar_carga(db, resolved_id, carga_id)


@router.get("/{carga_id}/registros", response_model=ProtheusCargaRegistrosPage)
def get_registros(
    carga_id: int,
    empresa_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(2000, ge=1, le=10000),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    resolved_id = resolve_empresa_id(context, empresa_id)
    carga = service.obter_carga(db, resolved_id, carga_id)
    total, registros = service.listar_registros(db, carga, skip, limit)
    return {"total": total, "skip": skip, "limit": limit, "registros": registros}


def _mensagem_enfileiramento(status: str, reutilizavel: bool) -> str:
    if reutilizavel:
        return "Ja existe carga concluida para empresa, data base e parametros informados."
    if status == "pendente":
        return "Carga enfileirada para processamento em background."
    if status == "processando":
        return "Carga ja esta em processamento."
    return "Carga registrada."
