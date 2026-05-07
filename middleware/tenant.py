# middleware/tenant.py
"""
Middleware de tenant - Contexto de empresa e isolamento de dados.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List

from db import get_db
from models import Usuario, UsuarioEmpresa, Empresa, Perfil
from .auth import CurrentUser, get_current_user


class EmpresaContext:
    """Contexto completo do usuario com empresa e permissoes."""

    def __init__(
        self,
        user_id: int,
        email: str,
        nome: str,
        is_admin: bool,
        empresa_id: Optional[int],
        empresa_nome: Optional[str],
        perfil_id: Optional[int],
        perfil_nome: Optional[str],
        permissoes: List[str],
    ):
        self.user_id = user_id
        self.email = email
        self.nome = nome
        self.is_admin = is_admin
        self.empresa_id = empresa_id
        self.empresa_nome = empresa_nome
        self.perfil_id = perfil_id
        self.perfil_nome = perfil_nome
        self.permissoes = permissoes

    def has_permission(self, permission: str) -> bool:
        """Verifica se o contexto tem uma permissao especifica."""
        # Admin tem todas as permissoes
        if self.is_admin:
            return True

        if "*" in self.permissoes:
            return True

        if permission in self.permissoes:
            return True

        # Verificar wildcard do recurso
        resource = permission.split(":")[0]
        if f"{resource}:*" in self.permissoes:
            return True

        return False

    def __repr__(self):
        return f"<EmpresaContext(user_id={self.user_id}, empresa_id={self.empresa_id}, permissoes={len(self.permissoes)})>"


def resolve_empresa_id(
    context: EmpresaContext,
    empresa_id: Optional[int] = None,
) -> int:
    """
    Resolve a empresa operacional da requisicao.

    Usuarios comuns sempre usam a empresa do token. Admins podem usar a
    empresa do token ou informar uma empresa explicitamente em rotas antigas.
    """
    if context.is_admin and empresa_id:
        return empresa_id

    if context.empresa_id:
        if empresa_id and empresa_id != context.empresa_id and not context.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voce nao tem acesso a esta empresa.",
            )
        return context.empresa_id

    if empresa_id and context.is_admin:
        return empresa_id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Nenhuma empresa selecionada. Por favor, selecione uma empresa.",
    )


async def get_empresa_context(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmpresaContext:
    """
    Dependency que obtem o contexto completo do usuario com empresa e permissoes.

    Raises:
        HTTPException 400: Se nenhuma empresa selecionada (para nao-admins)
        HTTPException 403: Se usuario nao tem acesso a empresa
    """
    empresa_id = current_user.empresa_id

    # Admin sem empresa selecionada - acesso total
    if current_user.is_admin and not empresa_id:
        return EmpresaContext(
            user_id=current_user.user_id,
            email=current_user.email,
            nome=current_user.nome,
            is_admin=True,
            empresa_id=None,
            empresa_nome=None,
            perfil_id=None,
            perfil_nome="Admin Master",
            permissoes=["*"],
        )

    # Usuario normal deve ter empresa selecionada
    if not empresa_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma empresa selecionada. Por favor, selecione uma empresa.",
        )

    # Verificar se usuario tem acesso a empresa
    usuario_empresa = (
        db.query(UsuarioEmpresa)
        .filter(
            UsuarioEmpresa.usuario_id == current_user.user_id,
            UsuarioEmpresa.empresa_id == empresa_id,
            UsuarioEmpresa.is_active == True,
        )
        .first()
    )

    if not usuario_empresa and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voce nao tem acesso a esta empresa.",
        )

    # Buscar empresa
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa nao encontrada.",
        )

    if not empresa.status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta empresa esta desativada.",
        )

    # Admin acessando qualquer empresa
    if current_user.is_admin and not usuario_empresa:
        return EmpresaContext(
            user_id=current_user.user_id,
            email=current_user.email,
            nome=current_user.nome,
            is_admin=True,
            empresa_id=empresa.id,
            empresa_nome=empresa.nome,
            perfil_id=None,
            perfil_nome="Admin Master",
            permissoes=["*"],
        )

    # Buscar perfil e permissoes
    perfil = db.query(Perfil).filter(Perfil.id == usuario_empresa.perfil_id).first()
    permissoes = perfil.permissoes if perfil else []

    return EmpresaContext(
        user_id=current_user.user_id,
        email=current_user.email,
        nome=current_user.nome,
        is_admin=current_user.is_admin,
        empresa_id=empresa.id,
        empresa_nome=empresa.nome,
        perfil_id=usuario_empresa.perfil_id,
        perfil_nome=perfil.nome if perfil else None,
        permissoes=permissoes,
    )


async def get_optional_empresa_context(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmpresaContext:
    """
    Similar a get_empresa_context, mas nao exige empresa selecionada.
    Util para endpoints que funcionam com ou sem empresa.
    """
    empresa_id = current_user.empresa_id

    if not empresa_id:
        return EmpresaContext(
            user_id=current_user.user_id,
            email=current_user.email,
            nome=current_user.nome,
            is_admin=current_user.is_admin,
            empresa_id=None,
            empresa_nome=None,
            perfil_id=None,
            perfil_nome=None,
            permissoes=["*"] if current_user.is_admin else [],
        )

    return await get_empresa_context(current_user, db)
