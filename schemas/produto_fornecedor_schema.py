from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal
from datetime import datetime
from models.produto_fornecedor import OperacaoConversao


class ProdutoFornecedorBase(BaseModel):
    produto_id: int
    empresa_id: Optional[int] = None
    cnpj_fornecedor: str
    razao_social_fornecedor: Optional[str] = None
    codigo_produto_fornecedor: str
    descricao_fornecedor: Optional[str] = None
    unidade_compra: str
    fator_conversao: Decimal
    operacao_conversao: OperacaoConversao
    unidade_convertida: str

    @field_validator("fator_conversao")
    @classmethod
    def fator_positivo(cls, v):
        if v <= 0:
            raise ValueError("Fator de conversao deve ser maior que zero")
        return v


class ProdutoFornecedorCreate(ProdutoFornecedorBase):
    pass


class ProdutoFornecedorUpdate(BaseModel):
    razao_social_fornecedor: Optional[str] = None
    codigo_produto_fornecedor: Optional[str] = None
    descricao_fornecedor: Optional[str] = None
    unidade_compra: Optional[str] = None
    fator_conversao: Optional[Decimal] = None
    operacao_conversao: Optional[OperacaoConversao] = None
    unidade_convertida: Optional[str] = None


class ProdutoFornecedorOut(ProdutoFornecedorBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
