"""
Schemas para efetivação de conciliações.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
from enum import Enum


class StatusConciliacao(str, Enum):
    """Status possíveis de uma conciliação."""
    PROCESSADA = "PROCESSADA"
    EFETIVADA = "EFETIVADA"


# ===================
# REQUEST SCHEMAS
# ===================

class EfetivarConciliacaoRequest(BaseModel):
    """Request para efetivar uma conciliação (dados JSON do FormData)."""
    empresa_id: int
    conta_contabil_id: int
    conta_contabil: str  # código da conta
    periodo: str  # "YYYY-MM"
    tipo_conciliacao: str = "receber"  # receber, pagar

    # Dados já processados (normalizados)
    base_origem: Dict[str, Any]  # { registros: [...] }
    base_contabil_filtrada: Dict[str, Any]  # { conta_contabil, registros: [...] }
    base_contabil_geral: Dict[str, Any]  # { registros: [...] }
    resultado: Dict[str, Any]  # resultado completo do processamento


# ===================
# RESPONSE SCHEMAS
# ===================

class EfetivarConciliacaoResponse(BaseModel):
    """Response após efetivar uma conciliação."""
    id: int
    message: str
    status: StatusConciliacao
    data_efetivacao: datetime


class ConciliacaoEfetivadaResumo(BaseModel):
    """Resumo de uma conciliação efetivada para listagem."""
    id: int
    empresa_id: int
    empresa_nome: Optional[str] = None
    conta_contabil_id: int
    conta_contabil_codigo: Optional[str] = None
    conta_contabil_descricao: Optional[str] = None
    periodo: str
    status: StatusConciliacao
    data_efetivacao: Optional[datetime] = None
    usuario_responsavel_id: Optional[int] = None
    usuario_responsavel_nome: Optional[str] = None

    # Resumo do resultado
    total_origem: Optional[float] = None
    total_destino: Optional[float] = None
    diferenca: Optional[float] = None
    situacao: Optional[str] = None
    tipo_conciliacao: Optional[str] = None  # banco, receber, pagar

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConciliacaoEfetivadaDetalhe(ConciliacaoEfetivadaResumo):
    """Detalhes completos de uma conciliação efetivada."""
    saldo: Decimal
    resultado_json: Optional[Dict[str, Any]] = None
    caminhos_arquivos: Optional[Dict[str, Dict[str, str]]] = None
    # Estrutura caminhos_arquivos:
    # {
    #   "origem": {"original": "path", "normalizado": "path"},
    #   "contabil_filtrado": {"original": "path", "normalizado": "path"},
    #   "contabil_geral": {"original": "path", "normalizado": "path"},
    #   "relatorio": {"json": "path"}
    # }


class ListaConciliacoesEfetivadas(BaseModel):
    """Lista paginada de conciliações efetivadas."""
    items: List[ConciliacaoEfetivadaResumo]
    total: int
    skip: int
    limit: int
    has_more: bool


class ContasEfetivadas(BaseModel):
    """Lista de IDs de contas já efetivadas para um período."""
    contas_efetivadas: List[int]


class ArquivoDownloadInfo(BaseModel):
    """Informações sobre arquivo disponível para download."""
    tipo_arquivo: str
    formato: str
    nome_arquivo: str
    caminho_arquivo: str
    tamanho_bytes: Optional[int] = None
    existe: bool


class ValidacaoEfetivacaoResponse(BaseModel):
    """Response para validação antes de efetivar."""
    pode_efetivar: bool
    motivo: Optional[str] = None
    divergencias: int = 0
    alertas: List[str] = []
