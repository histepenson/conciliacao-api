"""Schemas Pydantic para Balancete Contabil."""

from datetime import date, datetime
from typing import List

from pydantic import BaseModel


class BalanceteImportResult(BaseModel):
    """Resultado da importacao do balancete."""
    periodo: str
    total_linhas: int
    contas_casadas: int
    contas_nao_encontradas: List[str] = []


class BalanceteContaOut(BaseModel):
    """Linha do balancete de uma conta especifica."""
    id: int
    empresa_id: int
    conta_contabil_id: int | None = None
    conta_codigo_raw: str
    conta_codigo_normalizado: str
    descricao: str | None = None
    periodo: date
    saldo_anterior: float
    debito: float
    credito: float
    mov_periodo: float
    saldo_atual: float
    created_at: datetime

    class Config:
        from_attributes = True
