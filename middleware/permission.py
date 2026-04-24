# middleware/permission.py
"""
Middleware de permissoes - Verificacao de autorizacao.
"""
from functools import wraps
from typing import Callable, List, Union

from fastapi import Depends, HTTPException, status

from .auth import CurrentUser, get_current_user
from .tenant import EmpresaContext, get_empresa_context


def require_permission(permission: Union[str, List[str]]):
    """
    Dependency factory que verifica se o usuario tem a(s) permissao(oes) requerida(s).

    Uso:
        @router.get("/items")
        async def list_items(
            context: EmpresaContext = Depends(require_permission("item:read"))
        ):
            ...

        # Multiplas permissoes (OR - qualquer uma)
        @router.post("/items")
        async def create_item(
            context: EmpresaContext = Depends(require_permission(["item:write", "item:create"]))
        ):
            ...
    """
    permissions = [permission] if isinstance(permission, str) else permission

    async def _check_permission(
        context: EmpresaContext = Depends(get_empresa_context),
    ) -> EmpresaContext:
        # Admin tem todas as permissoes
        if context.is_admin:
            return context

        # Verificar se tem pelo menos uma das permissoes
        has_any = any(context.has_permission(p) for p in permissions)

        if not has_any:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissao negada. Requer: {', '.join(permissions)}",
            )

        return context

    return _check_permission


def require_all_permissions(permissions: List[str]):
    """
    Dependency factory que verifica se o usuario tem TODAS as permissoes requeridas.

    Uso:
        @router.delete("/items/{id}")
        async def delete_item(
            context: EmpresaContext = Depends(require_all_permissions(["item:read", "item:delete"]))
        ):
            ...
    """

    async def _check_all_permissions(
        context: EmpresaContext = Depends(get_empresa_context),
    ) -> EmpresaContext:
        # Admin tem todas as permissoes
        if context.is_admin:
            return context

        # Verificar se tem todas as permissoes
        missing = [p for p in permissions if not context.has_permission(p)]

        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissao negada. Faltam: {', '.join(missing)}",
            )

        return context

    return _check_all_permissions


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """
    Dependency que verifica se o usuario e admin master.

    Uso:
        @router.get("/admin/users")
        async def list_users(
            current_user: CurrentUser = Depends(require_admin)
        ):
            ...
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return current_user


def require_empresa_admin():
    """
    Dependency factory que verifica se o usuario e admin da empresa atual.

    Uso:
        @router.post("/empresa/users")
        async def add_user_to_empresa(
            context: EmpresaContext = Depends(require_empresa_admin())
        ):
            ...
    """

    async def _check_empresa_admin(
        context: EmpresaContext = Depends(get_empresa_context),
    ) -> EmpresaContext:
        # Admin master sempre pode
        if context.is_admin:
            return context

        # Verificar se tem permissao de admin da empresa
        if not context.has_permission("*"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso restrito a administradores da empresa.",
            )

        return context

    return _check_empresa_admin


# ============================================================
# CONSTANTES DE PERMISSOES
# ============================================================

class Permissions:
    """Constantes de permissoes do sistema."""

    # Administracao
    ADMIN_USERS = "admin:users"
    ADMIN_COMPANIES = "admin:companies"
    ADMIN_ROLES = "admin:roles"

    # Empresa
    EMPRESA_READ = "empresa:read"
    EMPRESA_WRITE = "empresa:write"

    # Plano de Contas
    PLANO_CONTAS_READ = "plano_contas:read"
    PLANO_CONTAS_WRITE = "plano_contas:write"
    PLANO_CONTAS_IMPORT = "plano_contas:import"

    # Conciliacao
    CONCILIACAO_READ = "conciliacao:read"
    CONCILIACAO_WRITE = "conciliacao:write"
    CONCILIACAO_DELETE = "conciliacao:delete"
    CONCILIACAO_EXPORT = "conciliacao:export"

    # Arquivos
    ARQUIVO_READ = "arquivo:read"
    ARQUIVO_UPLOAD = "arquivo:upload"
    ARQUIVO_DELETE = "arquivo:delete"

    # Relatorios
    RELATORIO_READ = "relatorio:read"
    RELATORIO_EXPORT = "relatorio:export"

    # Wildcard
    ALL = "*"


# Lista de todas as permissoes disponiveis (para validacao)
ALL_PERMISSIONS = [
    Permissions.ADMIN_USERS,
    Permissions.ADMIN_COMPANIES,
    Permissions.ADMIN_ROLES,
    Permissions.EMPRESA_READ,
    Permissions.EMPRESA_WRITE,
    Permissions.PLANO_CONTAS_READ,
    Permissions.PLANO_CONTAS_WRITE,
    Permissions.PLANO_CONTAS_IMPORT,
    Permissions.CONCILIACAO_READ,
    Permissions.CONCILIACAO_WRITE,
    Permissions.CONCILIACAO_DELETE,
    Permissions.CONCILIACAO_EXPORT,
    Permissions.ARQUIVO_READ,
    Permissions.ARQUIVO_UPLOAD,
    Permissions.ARQUIVO_DELETE,
    Permissions.RELATORIO_READ,
    Permissions.RELATORIO_EXPORT,
    Permissions.ALL,
]
