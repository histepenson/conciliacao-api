from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from middleware.permission import require_admin
from schemas.lancamento_padrao_ct2_layout_schema import (
    LpCt2LayoutCreate,
    LpCt2LayoutUpdate,
    LpCt2LayoutOut,
)
from services import admin_lp_ct2_layout_service as service


router = APIRouter(prefix="/admin/lp-ct2-layout", tags=["Admin - LP CT2 Layout"])


@router.get("", response_model=list[LpCt2LayoutOut])
def admin_listar_lp_ct2_layout(
    empresa_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return service.listar(db, empresa_id=empresa_id)


@router.post("", response_model=LpCt2LayoutOut)
def admin_criar_lp_ct2_layout(
    payload: LpCt2LayoutCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return service.criar(db, payload.model_dump())


@router.put("/{layout_id}", response_model=LpCt2LayoutOut)
def admin_atualizar_lp_ct2_layout(
    layout_id: int,
    payload: LpCt2LayoutUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return service.atualizar(db, layout_id, payload.model_dump(exclude_unset=True))


@router.delete("/{layout_id}")
def admin_deletar_lp_ct2_layout(
    layout_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return service.deletar(db, layout_id)
