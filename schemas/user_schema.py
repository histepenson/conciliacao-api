# schemas/user_schema.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ============================================================
# USUARIO - CREATE
# ============================================================

class UsuarioCreate(BaseModel):
    """Schema para criacao de usuario."""
    email: EmailStr
    nome: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)
    is_admin: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Senha deve ter no minimo 8 caracteres")
        if not any(c.isupper() for c in v):
            raise ValueError("Senha deve conter pelo menos uma letra maiuscula")
        if not any(c.islower() for c in v):
            raise ValueError("Senha deve conter pelo menos uma letra minuscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve conter pelo menos um numero")
        return v


# ============================================================
# USUARIO - UPDATE
# ============================================================

class UsuarioUpdate(BaseModel):
    """Schema para atualizacao de usuario."""
    email: Optional[EmailStr] = None
    nome: Optional[str] = Field(None, min_length=2, max_length=255)
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class UsuarioUpdatePassword(BaseModel):
    """Schema para atualizacao de senha pelo admin."""
    password: str = Field(..., min_length=8)


# ============================================================
# USUARIO - OUTPUT
# ============================================================

class UsuarioOut(BaseModel):
    """Schema de saida de usuario."""
    id: int
    email: str
    nome: str
    is_admin: bool
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UsuarioListOut(BaseModel):
    """Schema de saida para listagem de usuarios."""
    id: int
    email: str
    nome: str
    is_admin: bool
    is_active: bool
    empresas_count: int = 0
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UsuarioDetailOut(BaseModel):
    """Schema de saida detalhada de usuario."""
    id: int
    email: str
    nome: str
    is_admin: bool
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    empresas: List["UsuarioEmpresaOut"]

    class Config:
        from_attributes = True


# ============================================================
# USUARIO EMPRESA
# ============================================================

class UsuarioEmpresaCreate(BaseModel):
    """Schema para adicionar usuario a uma empresa."""
    empresa_id: int
    perfil_id: int


class UsuarioEmpresaUpdate(BaseModel):
    """Schema para atualizar associacao usuario-empresa."""
    perfil_id: Optional[int] = None
    is_active: Optional[bool] = None


class UsuarioEmpresaOut(BaseModel):
    """Schema de saida de associacao usuario-empresa."""
    id: int
    usuario_id: int
    usuario_nome: Optional[str] = None
    usuario_email: Optional[str] = None
    empresa_id: int
    empresa_nome: str
    empresa_cnpj: str
    perfil_id: int
    perfil_nome: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# PERFIL
# ============================================================

class PerfilCreate(BaseModel):
    """Schema para criacao de perfil."""
    nome: str = Field(..., min_length=2, max_length=100)
    descricao: Optional[str] = None
    permissoes: List[str] = []


class PerfilUpdate(BaseModel):
    """Schema para atualizacao de perfil."""
    nome: Optional[str] = Field(None, min_length=2, max_length=100)
    descricao: Optional[str] = None
    permissoes: Optional[List[str]] = None


class PerfilOut(BaseModel):
    """Schema de saida de perfil."""
    id: int
    nome: str
    descricao: Optional[str]
    permissoes: List[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# PAGINATION
# ============================================================

class PaginatedResponse(BaseModel):
    """Schema generico para respostas paginadas."""
    items: List
    total: int
    page: int
    per_page: int
    pages: int


class UsuariosPaginatedResponse(BaseModel):
    """Schema para listagem paginada de usuarios."""
    items: List[UsuarioListOut]
    total: int
    page: int
    per_page: int
    pages: int


# Rebuild models para resolver forward references
UsuarioDetailOut.model_rebuild()
