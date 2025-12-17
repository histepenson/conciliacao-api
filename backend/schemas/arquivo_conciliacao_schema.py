from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class ArquivoConciliacaoBase(BaseModel):
    """Schema base para ArquivoConciliacao - alinhado com o modelo SQLAlchemy"""
    conciliacao_id: int
    caminho_arquivo: str
    data_conciliacao: datetime


class ArquivoConciliacaoCreate(ArquivoConciliacaoBase):
    """Schema para criar um novo arquivo de conciliação"""
    pass


class ArquivoConciliacaoUpdate(BaseModel):
    """Schema para atualizar arquivo (todos campos opcionais)"""
    caminho_arquivo: Optional[str] = None
    data_conciliacao: Optional[datetime] = None


class ArquivoConciliacaoResponse(ArquivoConciliacaoBase):
    """Schema para retornar dados do arquivo (inclui ID e timestamps)"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# Alias para compatibilidade
ArquivoConciliacaoOut = ArquivoConciliacaoResponse