from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.tenant import EmpresaContext, get_empresa_context, resolve_empresa_id
from services import lancamento_padrao_service as service

router = APIRouter(prefix="/v1/lancamentos-padrao", tags=["Lancamentos Padrao"])


@router.get("")
def listar(
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    eid = resolve_empresa_id(context, empresa_id)
    return service.listar(db, eid)


@router.post("")
def criar(
    body: dict[str, Any],
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    eid = resolve_empresa_id(context, empresa_id)
    return service.criar(db, eid, body)


@router.get("/{lp_id}")
def obter(
    lp_id: int,
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    eid = resolve_empresa_id(context, empresa_id)
    return service.obter(db, lp_id, eid)


@router.put("/{lp_id}")
def atualizar(
    lp_id: int,
    body: dict[str, Any],
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    eid = resolve_empresa_id(context, empresa_id)
    return service.atualizar(db, lp_id, eid, body)


@router.put("/bulk/grupo")
def bulk_grupo(
    body: dict[str, Any],
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    context: EmpresaContext = Depends(get_empresa_context),
):
    """body: {ids: [1,2,3], grupo: "NOME"} — grupo null/vazio remove o grupo."""
    eid = resolve_empresa_id(context, empresa_id)
    ids = body.get("ids", [])
    grupo = body.get("grupo") or None
    atualizados = service.bulk_definir_grupo(db, eid, ids, grupo)
    return {"atualizados": atualizados}
