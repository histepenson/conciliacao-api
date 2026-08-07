from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LeasingRegraClassificacaoBase(BaseModel):
    empresa_id: Optional[int] = None
    padrao_cliente: str
    natureza_codigo: str
    ativo: bool = True


class LeasingRegraClassificacaoCreate(LeasingRegraClassificacaoBase):
    pass


class LeasingRegraClassificacaoUpdate(BaseModel):
    padrao_cliente: Optional[str] = None
    natureza_codigo: Optional[str] = None
    ativo: Optional[bool] = None


class LeasingRegraClassificacaoResponse(LeasingRegraClassificacaoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
