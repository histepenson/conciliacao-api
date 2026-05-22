from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from middleware.permission import require_admin
from schemas.empresa_schema import EmpresaCreate, EmpresaUpdate, EmpresaResponse
from schemas.user_schema import UsuarioEmpresaOut
from services.admin_empresa_service import (
    listar_empresas,
    obter_empresa,
    criar_empresa,
    atualizar_empresa,
    desativar_empresa,
    listar_usuarios_da_empresa,
)


router = APIRouter(prefix="/admin/empresas", tags=["Admin - Empresas"])


@router.get("", response_model=list[EmpresaResponse])
def admin_listar_empresas(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return listar_empresas(db)


@router.get("/{empresa_id}", response_model=EmpresaResponse)
def admin_obter_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return obter_empresa(db, empresa_id)


@router.post("", response_model=EmpresaResponse)
def admin_criar_empresa(
    payload: EmpresaCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return criar_empresa(db, payload.model_dump())


@router.put("/{empresa_id}", response_model=EmpresaResponse)
def admin_atualizar_empresa(
    empresa_id: int,
    payload: EmpresaUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return atualizar_empresa(db, empresa_id, payload.model_dump(exclude_unset=True))


@router.delete("/{empresa_id}")
def admin_desativar_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return desativar_empresa(db, empresa_id)


@router.get("/{empresa_id}/usuarios", response_model=list[UsuarioEmpresaOut])
def admin_usuarios_da_empresa(
    empresa_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return listar_usuarios_da_empresa(db, empresa_id)
