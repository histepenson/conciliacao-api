from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class PlanoDeContasBase(BaseModel):
    """Schema base para Plano de Contas - alinhado com o modelo SQLAlchemy"""
    empresa_id: int
    conta_contabil: str
    descricao: str
    tipo_conta: str
    conciliavel: bool = False
    conta_superior: Optional[str] = None


class PlanoDeContasCreate(PlanoDeContasBase):
    """Schema para criar uma nova conta"""
    pass


class PlanoDeContasUpdate(BaseModel):
    """Schema para atualizar conta (todos campos opcionais)"""
    conta_contabil: Optional[str] = None
    tipo_conta: Optional[str] = None
    descricao: Optional[str] = None
    conciliavel: Optional[bool] = None
    conta_superior: Optional[str] = None


class PlanoDeContasResponse(PlanoDeContasBase):
    """Schema para retornar dados da conta"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# Alias para compatibilidade
PlanoDeContasOut = PlanoDeContasResponse


# ============================================================
# SCHEMAS PARA IMPORTAÇÃO
# ============================================================

class ImportacaoResultado(BaseModel):
    """Resultado da importação de plano de contas"""
    mensagem: str
    total_linhas: int
    importados: int
    atualizados: int
    erros: int
    detalhes_erros: Optional[List[Dict[str, Any]]] = None
    
    model_config = ConfigDict(from_attributes=True)


class ImportacaoErro(BaseModel):
    """Detalhes de erro durante importação"""
    linha: int
    codigo_conta: Optional[str] = None
    erro: str
