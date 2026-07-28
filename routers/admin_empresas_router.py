from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from middleware.auth import CurrentUser, get_current_user
from middleware.permission import require_admin
from schemas.empresa_schema import EmpresaCreate, EmpresaUpdate, EmpresaResponse
from schemas.empresa_configuracao_schema import EmpresaConfiguracaoOut, EmpresaConfiguracaoSet
from schemas.user_schema import UsuarioEmpresaOut
from services.admin_empresa_service import (
    listar_empresas,
    obter_empresa,
    criar_empresa,
    atualizar_empresa,
    desativar_empresa,
    listar_usuarios_da_empresa,
)
from services.empresa_configuracao_service import (
    listar_configuracoes,
    definir_configuracao,
    remover_configuracao,
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


@router.get("/{empresa_id}/configuracoes", response_model=list[EmpresaConfiguracaoOut])
def admin_listar_configuracoes(
    empresa_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return listar_configuracoes(db, empresa_id)


@router.put("/{empresa_id}/configuracoes/{chave}", response_model=EmpresaConfiguracaoOut)
def admin_definir_configuracao(
    empresa_id: int,
    chave: str,
    payload: EmpresaConfiguracaoSet,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
    current_user: CurrentUser = Depends(get_current_user),
):
    return definir_configuracao(db, empresa_id, chave, payload.valor, current_user.user_id)


@router.delete("/{empresa_id}/configuracoes/{chave}")
def admin_remover_configuracao(
    empresa_id: int,
    chave: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
    current_user: CurrentUser = Depends(get_current_user),
):
    return remover_configuracao(db, empresa_id, chave, current_user.user_id)
