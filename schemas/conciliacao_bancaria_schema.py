"""
Schemas Pydantic para Conciliacao Bancaria.

Define estruturas de entrada e saida para o endpoint de conciliacao bancaria.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator


# =======================
# ENTRADA
# =======================

class BaseExtratoBancario(BaseModel):
    """Base financeira - FINR470 (extrato bancario). Uma conta bancaria fisica."""
    registros: List[Dict[str, Any]]
    identificacao: Optional[str] = None


class BaseRazaoBanco(BaseModel):
    """Base contabil - CTBR400 (razao contabil do banco)."""
    registros: List[Dict[str, Any]]
    conta_contabil: str
    conta_contabil_id: Optional[int] = None


class ParametrosConciliacaoBancaria(BaseModel):
    """Parametros adicionais para a conciliacao bancaria."""
    data_base: str
    empresa_id: Optional[int] = None


class RequestConciliacaoBancaria(BaseModel):
    """Request para processar conciliacao bancaria."""
    base_extrato: List[BaseExtratoBancario]
    base_razao: BaseRazaoBanco
    parametros: ParametrosConciliacaoBancaria

    @field_validator("base_extrato", mode="before")
    @classmethod
    def _wrap_single_extrato(cls, v):
        """Aceita tambem o formato antigo (um unico objeto), envolvendo em lista."""
        if isinstance(v, dict):
            return [v]
        return v


class EfetivarConciliacaoBancariaRequest(BaseModel):
    """Request para efetivar conciliacao bancaria."""
    empresa_id: int
    conta_contabil_id: int
    conta_contabil: str
    data_base: str  # DD/MM/YYYY
    resultado: Dict[str, Any]


# =======================
# SAIDA
# =======================

class MovimentoExtrato(BaseModel):
    """Movimento do extrato bancario normalizado."""
    data: str
    documento: str
    prefixo: str
    numero: str
    chave_documento: str  # prefixo + numero normalizado
    descricao: str
    entrada: float = 0.0
    saida: float = 0.0
    valor: float  # positivo = entrada, negativo = saida
    tipo: str  # ENTRADA ou SAIDA
    saldo_atual: float = 0.0
    conta_origem: str = ""  # Identificacao da conta bancaria de origem (quando ha mais de uma)


class MovimentoRazao(BaseModel):
    """Movimento do razao contabil normalizado."""
    data: str
    lote_doc: str
    historico: str
    documento_extraido: str  # documento extraido do historico
    prefixo: str
    numero: str
    chave_documento: str  # prefixo + numero normalizado
    debito: float = 0.0
    credito: float = 0.0
    valor: float  # positivo = debito, negativo = credito
    tipo: str  # DEBITO ou CREDITO
    saldo_atual: float = 0.0


class DiferencaBancaria(BaseModel):
    """Diferenca encontrada na conciliacao bancaria."""
    chave_documento: str
    documento_extrato: str
    documento_razao: str
    data_extrato: Optional[str] = None
    data_razao: Optional[str] = None
    valor_extrato: float = 0.0
    valor_razao: float = 0.0
    diferenca: float
    tipo_diferenca: str  # SO_FINANCEIRO, SO_CONTABILIDADE, DIVERGENCIA_VALOR, DIVERGENCIA_SINAL, DIVERGENCIA_DATA, CONCILIADO
    descricao_extrato: str = ""
    historico_razao: str = ""
    status: str  # verde ou vermelho
    observacao: str = ""


class RegistroSoExtrato(BaseModel):
    """Registro que existe apenas no extrato bancario."""
    data: str
    documento: str = ""
    prefixo: str = ""
    numero: str = ""
    descricao: str = ""
    valor: float
    tipo: str  # ENTRADA ou SAIDA
    conta_origem: str = ""  # Identificacao da conta bancaria de origem (quando ha mais de uma)


class RegistroSoRazao(BaseModel):
    """Registro que existe apenas no razao contabil."""
    data: str
    lote_doc: str = ""
    historico: str = ""
    documento_extraido: str = ""
    prefixo: str = ""
    numero: str = ""
    valor: float
    tipo: str  # DEBITO ou CREDITO


class MovimentoDia(BaseModel):
    """Movimento agrupado por dia."""
    data: str
    entradas_extrato: float = 0.0
    saidas_extrato: float = 0.0
    debitos_razao: float = 0.0
    creditos_razao: float = 0.0
    dif_entradas: float = 0.0
    dif_saidas: float = 0.0
    status: str  # CONCILIADO ou DIVERGENTE
    # Detalhes dos registros NAO conciliados (pendentes) - vermelho
    so_extrato_entradas: List[Dict[str, Any]] = []
    so_extrato_saidas: List[Dict[str, Any]] = []
    so_razao_debitos: List[Dict[str, Any]] = []
    so_razao_creditos: List[Dict[str, Any]] = []
    # Detalhes dos registros CONCILIADOS (matched) - verde
    conciliados_extrato_entradas: List[Dict[str, Any]] = []
    conciliados_extrato_saidas: List[Dict[str, Any]] = []
    conciliados_razao_debitos: List[Dict[str, Any]] = []
    conciliados_razao_creditos: List[Dict[str, Any]] = []


class ResumoConciliacaoBancaria(BaseModel):
    """Resumo da conciliacao bancaria por dia."""
    total_entradas_extrato: float = 0.0
    total_saidas_extrato: float = 0.0
    total_debitos_razao: float = 0.0
    total_creditos_razao: float = 0.0
    dif_total_entradas: float = 0.0
    dif_total_saidas: float = 0.0
    situacao: str  # CONCILIADO ou DIVERGENTE

    # Quantidades de dias
    qtd_dias: int = 0
    qtd_conciliados: int = 0
    qtd_divergentes: int = 0

    # Percentuais
    percentual_conciliacao: float = 0.0

    data_processamento: str = ""


class RelatorioConciliacaoBancaria(BaseModel):
    """Relatorio completo da conciliacao bancaria."""
    resumo: Dict[str, Any]

    # Movimentos agrupados por dia
    movimentos_por_dia: List[Dict[str, Any]] = []

    # Dias divergentes e conciliados
    dias_divergentes: List[Dict[str, Any]] = []
    dias_conciliados: List[Dict[str, Any]] = []

    # Registros sem correspondencia (analise detalhada)
    registros_so_extrato: List[Dict[str, Any]] = []
    registros_so_razao: List[Dict[str, Any]] = []

    observacoes: List[str] = []
    alertas: List[str] = []
