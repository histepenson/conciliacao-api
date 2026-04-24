from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from middleware.permission import require_admin
from schemas.user_schema import (
    UsuarioCreate,
    UsuarioUpdate,
    UsuarioOut,
    UsuarioListOut,
    UsuarioDetailOut,
    UsuarioEmpresaCreate,
)
from services.admin_user_service import (
    listar_usuarios,
    obter_usuario,
    criar_usuario,
    atualizar_usuario,
    desativar_usuario,
    adicionar_usuario_empresa,
    remover_usuario_empresa,
)


router = APIRouter(prefix="/admin/usuarios", tags=["Admin - Usuarios"])


@router.get("/", response_model=list[UsuarioListOut])
def admin_listar_usuarios(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return listar_usuarios(db)


@router.get("/{usuario_id}", response_model=UsuarioDetailOut)
def admin_obter_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return obter_usuario(db, usuario_id)


@router.post("/", response_model=UsuarioOut)
def admin_criar_usuario(
    payload: UsuarioCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return criar_usuario(db, payload.model_dump())


@router.put("/{usuario_id}", response_model=UsuarioOut)
def admin_atualizar_usuario(
    usuario_id: int,
    payload: UsuarioUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return atualizar_usuario(db, usuario_id, payload.model_dump(exclude_unset=True))


@router.delete("/{usuario_id}")
def admin_desativar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return desativar_usuario(db, usuario_id)


@router.get("/{usuario_id}/empresas")
def admin_listar_usuario_empresas(
    usuario_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Lista as empresas vinculadas a um usuario."""
    usuario = obter_usuario(db, usuario_id)
    return usuario.get("empresas", [])


@router.post("/{usuario_id}/empresas")
def admin_adicionar_usuario_empresa(
    usuario_id: int,
    payload: UsuarioEmpresaCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return adicionar_usuario_empresa(db, usuario_id, payload.empresa_id, payload.perfil_id)


@router.delete("/{usuario_id}/empresas/{empresa_id}")
def admin_remover_usuario_empresa(
    usuario_id: int,
    empresa_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    return remover_usuario_empresa(db, usuario_id, empresa_id)
