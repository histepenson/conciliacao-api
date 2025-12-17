from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ConciliacaoBase(BaseModel):
    """Schema base para Conciliação - alinhado com o modelo SQLAlchemy"""
    empresa_id: int
    conta_contabil_id: int
    periodo: str  # Ex: "2025-01" ou "01/2025"
    saldo: Decimal  # ← DECIMAL no modelo, não float


class ConciliacaoCreate(ConciliacaoBase):
    """Schema para criar uma conciliação"""
    pass


class ConciliacaoUpdate(BaseModel):
    """Schema para atualizar conciliação (todos campos opcionais)"""
    empresa_id: Optional[int] = None
    conta_contabil_id: Optional[int] = None
    periodo: Optional[str] = None
    saldo: Optional[Decimal] = None


class ConciliacaoResponse(ConciliacaoBase):
    """Schema para retornar dados da conciliação"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Alias para compatibilidade
ConciliacaoOut = ConciliacaoResponse