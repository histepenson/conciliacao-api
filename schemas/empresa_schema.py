from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class EmpresaBase(BaseModel):
    nome: str
    cnpj: str
    status: bool = True
    permite_efetivar_divergente: bool = False
    protheus_tenant: Optional[str] = None
    protheus_url: Optional[str] = None
    protheus_rest_prefix: Optional[str] = None
    protheus_user: Optional[str] = None


class EmpresaCreate(EmpresaBase):
    protheus_password: Optional[str] = None


class EmpresaUpdate(BaseModel):
    nome: Optional[str] = None
    cnpj: Optional[str] = None
    status: Optional[bool] = None
    permite_efetivar_divergente: Optional[bool] = None
    protheus_tenant: Optional[str] = None
    protheus_url: Optional[str] = None
    protheus_rest_prefix: Optional[str] = None
    protheus_user: Optional[str] = None
    protheus_password: Optional[str] = None


class EmpresaResponse(EmpresaBase):
    id: int
    created_at: datetime
    updated_at: datetime
    usuarios_count: int = 0
    protheus_password_configurada: bool = False

    model_config = {"from_attributes": True}


# Alias para compatibilidade com routers que usam EmpresaOut
EmpresaOut = EmpresaResponse