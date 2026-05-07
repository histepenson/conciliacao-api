from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from middleware.permission import require_admin
from schemas.user_schema import PerfilCreate, PerfilUpdate, PerfilOut
from services.admin_perfil_service import (
    listar_perfis,
    obter_perfil,
    criar_perfil,
    atualizar_perfil,
    deletar_perfil,
)


router = APIRouter(prefix="/admin/perfis", tags=["Admin - Perfis"])


@router.get("", response_model=list[PerfilOut])
def admin_listar_perfis(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return listar_perfis(db)


@router.get("/{perfil_id}", response_model=PerfilOut)
def admin_obter_perfil(
    perfil_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return obter_perfil(db, perfil_id)


@router.post("", response_model=PerfilOut)
def admin_criar_perfil(
    payload: PerfilCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return criar_perfil(db, payload.model_dump())


@router.put("/{perfil_id}", response_model=PerfilOut)
def admin_atualizar_perfil(
    perfil_id: int,
    payload: PerfilUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return atualizar_perfil(db, perfil_id, payload.model_dump(exclude_unset=True))


@router.delete("/{perfil_id}")
def admin_deletar_perfil(
    perfil_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return deletar_perfil(db, perfil_id)
