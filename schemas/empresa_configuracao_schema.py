from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EmpresaConfiguracaoSet(BaseModel):
    valor: Any


class EmpresaConfiguracaoOut(BaseModel):
    id: int
    empresa_id: int
    chave: str
    valor: Any
    criado_em: datetime
    atualizado_em: datetime

    class Config:
        from_attributes = True
