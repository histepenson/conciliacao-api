from pydantic import BaseModel, field_validator
from typing import Optional
from decimal import Decimal
from datetime import date, datetime
from models.estoque import TipoMovimentacao


class SaldoOut(BaseModel):
    id: int
    empresa_id: int
    produto_id: int
    periodo: date
    saldo_inicial: Decimal
    entradas: Decimal
    saidas: Decimal
    ajustes: Decimal
    saldo_final: Decimal
    fechado: bool
    updated_at: Optional[datetime] = None

    # campos enriquecidos pelo service
    produto_codigo: Optional[str] = None
    produto_descricao: Optional[str] = None
    produto_unidade: Optional[str] = None
    alerta_negativo: bool = False

    model_config = {"from_attributes": True}


class MovimentacaoOut(BaseModel):
    id: int
    empresa_id: int
    produto_id: int
    data_movimentacao: date
    tipo: TipoMovimentacao
    quantidade: Decimal
    documento_origem: Optional[str] = None
    justificativa: Optional[str] = None
    created_at: datetime

    produto_codigo: Optional[str] = None
    produto_descricao: Optional[str] = None

    model_config = {"from_attributes": True}


class AjusteRequest(BaseModel):
    empresa_id: Optional[int] = None
    produto_id: int
    quantidade: Decimal
    justificativa: str
    data_movimentacao: Optional[date] = None

    @field_validator("justificativa")
    @classmethod
    def justificativa_obrigatoria(cls, v):
        if not v or not v.strip():
            raise ValueError("Justificativa e obrigatoria para ajustes manuais")
        return v.strip()


class ReprocessarRequest(BaseModel):
    empresa_id: Optional[int] = None
    periodo: date


class FechamentoRequest(BaseModel):
    empresa_id: Optional[int] = None
    periodo: date


class FechamentoOut(BaseModel):
    periodo: date
    produtos_fechados: int
    message: str


class ReaberturaRequest(BaseModel):
    empresa_id: Optional[int] = None
    periodo: date
