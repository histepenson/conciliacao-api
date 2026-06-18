"""
Schemas Pydantic para Conciliacao de Impostos.

Compara lancamentos de debito do razao contabil (CT2RAZCT5, via ct2_key) contra
uma coluna de valor de imposto do SFT (Entradas Fiscais) escolhida pelo usuario
para a conta contabil em questao (ex: Valor ICMS, Valor PIS, Valor COFINS).
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel


# =======================
# ENTRADA
# =======================

class BaseSftImpostos(BaseModel):
    """Base fiscal - SFTENT (entradas fiscais)."""
    registros: List[Dict[str, Any]]


class BaseRazaoImpostos(BaseModel):
    """Base contabil - CT2RAZCT5 (razao com ct2_key)."""
    registros: List[Dict[str, Any]]
    conta_contabil: str
    conta_contabil_id: Optional[int] = None


class ParametrosConciliacaoImpostos(BaseModel):
    """Parametros adicionais para a conciliacao de impostos."""
    data_base: str
    empresa_id: Optional[int] = None
    campo_imposto: str  # ex: valicm, valpis, valcof, valipi, icmsret, difal
    tipo_mov: Optional[str] = None  # "ENTRADA" ou "SAIDA" - filtra a coluna Tipo Mov do SFT


class RequestConciliacaoImpostos(BaseModel):
    """Request para processar conciliacao de impostos."""
    base_sft: BaseSftImpostos
    base_razao: BaseRazaoImpostos
    parametros: ParametrosConciliacaoImpostos


class EfetivarConciliacaoImpostosRequest(BaseModel):
    """Request para efetivar conciliacao de impostos."""
    empresa_id: int
    conta_contabil_id: int
    conta_contabil: str
    data_base: str  # DD/MM/YYYY
    campo_imposto: str
    resultado: Dict[str, Any]


# =======================
# SAIDA
# =======================

class ResumoConciliacaoImpostos(BaseModel):
    """Resumo da conciliacao de impostos."""
    campo_imposto: str
    coluna_razao: str = "debito"  # "debito" (Entrada) ou "credito" (Saida)
    total_lancamento_razao: float = 0.0
    total_debito_razao: float = 0.0
    total_credito_razao: float = 0.0
    total_sft: float = 0.0
    diferenca: float = 0.0
    situacao: str  # CONCILIADO ou DIVERGENTE
    qtd_lancamentos_razao: int = 0
    qtd_registros_sft: int = 0
    qtd_matched: int = 0


class RelatorioConciliacaoImpostos(BaseModel):
    """Relatorio completo da conciliacao de impostos."""
    resumo: Dict[str, Any]

    # Lancamentos de debito do razao sem correspondencia no SFT
    diferencas_so_razao: List[Dict[str, Any]] = []
    # Notas do SFT sem correspondencia no razao
    diferencas_so_sft: List[Dict[str, Any]] = []

    observacoes: List[str] = []
    alertas: List[str] = []
