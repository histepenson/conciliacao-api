# schemas/auth_schema.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ============================================================
# LOGIN
# ============================================================

class LoginRequest(BaseModel):
    """Schema para requisicao de login."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Schema para resposta de login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos
    user: "UserInfo"
    empresas: List["EmpresaInfo"]


# ============================================================
# TOKEN
# ============================================================

class RefreshTokenRequest(BaseModel):
    """Schema para renovacao de token."""
    refresh_token: str


class TokenResponse(BaseModel):
    """Schema para resposta de token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============================================================
# PASSWORD RESET
# ============================================================

class ForgotPasswordRequest(BaseModel):
    """Schema para solicitacao de reset de senha."""
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Schema para resposta de solicitacao de reset."""
    message: str = "Se o email existir, voce recebera instrucoes para redefinir sua senha."


class ResetPasswordRequest(BaseModel):
    """Schema para redefinicao de senha."""
    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
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


class ResetPasswordResponse(BaseModel):
    """Schema para resposta de redefinicao de senha."""
    message: str = "Senha redefinida com sucesso."


class ChangePasswordRequest(BaseModel):
    """Schema para alteracao de senha (usuario logado)."""
    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Senha deve ter no minimo 8 caracteres")
        return v


# ============================================================
# EMPRESA SELECTION
# ============================================================

class SelectEmpresaRequest(BaseModel):
    """Schema para selecao de empresa."""
    empresa_id: int


class SelectEmpresaResponse(BaseModel):
    """Schema para resposta de selecao de empresa."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    empresa: "EmpresaInfo"
    permissoes: List[str]


# ============================================================
# USER INFO
# ============================================================

class UserInfo(BaseModel):
    """Informacoes basicas do usuario."""
    id: int
    email: str
    nome: str
    is_admin: bool

    class Config:
        from_attributes = True


class UserMe(BaseModel):
    """Informacoes completas do usuario logado."""
    id: int
    email: str
    nome: str
    is_admin: bool
    is_active: bool
    email_verified: bool
    created_at: datetime
    last_login: Optional[datetime]
    empresa_atual: Optional["EmpresaInfo"]
    permissoes: List[str]
    empresas: List["EmpresaInfo"]

    class Config:
        from_attributes = True


class EmpresaInfo(BaseModel):
    """Informacoes basicas da empresa."""
    id: int
    nome: str
    cnpj: str
    status: bool
    perfil: Optional[str] = None  # Nome do perfil do usuario nesta empresa

    class Config:
        from_attributes = True


# ============================================================
# PERFIL
# ============================================================

class PerfilInfo(BaseModel):
    """Informacoes do perfil."""
    id: int
    nome: str
    descricao: Optional[str]
    permissoes: List[str]
    is_system: bool

    class Config:
        from_attributes = True


# Rebuild models para resolver forward references
LoginResponse.model_rebuild()
SelectEmpresaResponse.model_rebuild()
UserMe.model_rebuild()
