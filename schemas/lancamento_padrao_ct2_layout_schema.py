from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

# Campos canonicos aceitos em layout_campos -- precisa bater exatamente com
# as chaves de CAMPOS_CT2_CANONICOS em tools/estoque/calc_diferencas_estoque.py
CAMPOS_CT2_VALIDOS = {"produto", "armazem", "loja", "item", "doc", "serie", "parceiro", "data", "numseq"}


class CampoLayoutCt2(BaseModel):
    campo: str
    inicio: int
    tamanho: int

    @field_validator("campo")
    @classmethod
    def validar_campo(cls, v: str) -> str:
        if v not in CAMPOS_CT2_VALIDOS:
            raise ValueError(f"campo invalido: {v!r} -- valores aceitos: {sorted(CAMPOS_CT2_VALIDOS)}")
        return v

    @field_validator("inicio")
    @classmethod
    def validar_inicio(cls, v: int) -> int:
        if v < 0:
            raise ValueError("inicio nao pode ser negativo")
        return v

    @field_validator("tamanho")
    @classmethod
    def validar_tamanho(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("tamanho precisa ser maior que zero")
        return v


class LpCt2LayoutCreate(BaseModel):
    empresa_id: int
    lp_codigo: str
    tipo_chave: Optional[str] = None  # "ESTOQUE" | "COMPRA" | "VENDA" -- usado quando CT2_KEY vem preenchido
    codigo_movimento_ct2_vazio: Optional[str] = None  # ex.: "RE1" -- usado quando CT2_KEY vem vazio
    layout_campos: Optional[List[CampoLayoutCt2]] = None  # layout generico por campo/posicao (matching de Estoque)
    descricao: Optional[str] = None


class LpCt2LayoutUpdate(BaseModel):
    tipo_chave: Optional[str] = None
    codigo_movimento_ct2_vazio: Optional[str] = None
    layout_campos: Optional[List[CampoLayoutCt2]] = None
    descricao: Optional[str] = None


class LpCt2LayoutOut(BaseModel):
    id: int
    empresa_id: int
    lp_codigo: str
    tipo_chave: Optional[str] = None
    codigo_movimento_ct2_vazio: Optional[str] = None
    layout_campos: Optional[List[CampoLayoutCt2]] = None
    descricao: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
