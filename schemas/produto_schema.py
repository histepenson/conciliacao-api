from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ProdutoBase(BaseModel):
    empresa_id: Optional[int] = None
    codigo_interno: str
    descricao: str
    ncm: Optional[str] = None
    unidade_estoque: str
    ativo: bool = True


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoUpdate(BaseModel):
    codigo_interno: Optional[str] = None
    descricao: Optional[str] = None
    ncm: Optional[str] = None
    unidade_estoque: Optional[str] = None
    ativo: Optional[bool] = None


class ProdutoOut(ProdutoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
