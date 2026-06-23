"""
Schemas Pydantic para Conciliacao de Estoque.

Define estruturas de entrada e saida para o endpoint de conciliacao de estoque.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel


# =======================
# ENTRADA
# =======================

class BaseKardex(BaseModel):
    """Base do Kardex - movimentacao de estoque."""
    registros: List[Dict[str, Any]]


class BaseRazaoEstoque(BaseModel):
    """Base contabil - CTBR400 (razao contabil de estoque)."""
    registros: List[Dict[str, Any]]
    conta_contabil: str
    conta_contabil_id: Optional[int] = None


class ParametrosConciliacaoEstoque(BaseModel):
    """Parametros adicionais para a conciliacao de estoque."""
    data_base: str
    empresa_id: Optional[int] = None


class RequestConciliacaoEstoque(BaseModel):
    """Request para processar conciliacao de estoque."""
    base_kardex: BaseKardex
    base_razao: BaseRazaoEstoque
    parametros: ParametrosConciliacaoEstoque


# =======================
# SAIDA
# =======================

class MovimentoGrupo(BaseModel):
    """Movimento agrupado por (data, codigo_movimento)."""
    data: str
    codigo_movimento: str
    tipo_movimento: str
    valor_kardex: float = 0.0
    valor_razao: float = 0.0
    debito_razao: float = 0.0
    credito_razao: float = 0.0
    diferenca: float = 0.0
    diferenca_abs: float = 0.0
    status: str
    origem: str


class ResumoConciliacaoEstoque(BaseModel):
    """Resumo da conciliacao de estoque."""
    total_kardex: float = 0.0
    total_razao: float = 0.0
    dif_total: float = 0.0
    situacao: str
    qtd_grupos: int = 0
    qtd_conciliados: int = 0
    qtd_divergentes: int = 0
    qtd_so_kardex: int = 0
    qtd_so_razao: int = 0
    percentual_conciliacao: float = 0.0
    data_processamento: str = ""


class RegistroSoKardex(BaseModel):
    """Registro que existe apenas no Kardex."""
    data: str
    cf: str = ""
    codigo_movimento: str = ""
    tipo_movimento: str = ""
    valor: float = 0.0
    documento_numero: str = ""
    descricao: str = ""
    codigo_produto: str = ""


class RegistroSoRazao(BaseModel):
    """Registro que existe apenas no Razao contabil."""
    data_movimento: str
    data_lancamento: str = ""
    codigo_movimento: str = ""
    historico: str = ""
    lote_doc: str = ""
    debito: float = 0.0
    credito: float = 0.0
    valor: float = 0.0
    tipo: str = ""


class RelatorioConciliacaoEstoque(BaseModel):
    """Relatorio completo da conciliacao de estoque."""
    resumo: Dict[str, Any]
    movimentos_por_grupo: List[Dict[str, Any]] = []
    grupos_divergentes: List[Dict[str, Any]] = []
    grupos_conciliados: List[Dict[str, Any]] = []
    observacoes: List[str] = []
    alertas: List[str] = []
