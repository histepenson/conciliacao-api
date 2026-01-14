from pydantic import BaseModel,field_validator
from typing import Optional
from datetime import datetime


class EmpresaBase(BaseModel):
    nome: str
    cnpj: str
    status: bool = True

class EmpresaCreate(EmpresaBase):
    pass


class EmpresaUpdate(BaseModel):
    nome: Optional[str] = None
    cnpj: Optional[str] = None
    status: Optional[bool] = None


class EmpresaResponse(EmpresaBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Alias para compatibilidade com routers que usam EmpresaOut
EmpresaOut = EmpresaResponse