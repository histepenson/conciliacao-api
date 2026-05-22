"""
Modulo de processamento de Contas a Receber.

Processa planilhas de contas a receber (clientes) extraindo:
- Codigo do cliente (formato C{base}{loja})
- Nome do cliente
- Valor total (vencido + a vencer)
- Dias vencidos
- Classificacao de prazo
"""

import logging
from typing import Any

import pandas as pd

from .base import (
    ProcessadorFinanceiroBase,
    ConfiguracaoColunas,
    TipoFinanceiro,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURACAO DE COLUNAS PARA CONTAS A RECEBER
# =============================================================================

CONFIGURACAO_CONTAS_RECEBER = ConfiguracaoColunas(
    # Colunas de identificacao do cliente
    codigo_cliente=[
        "codigo_lj_nome_do_cliente",
        "codigo_lj_nome_do_cliente_",
        "codigo_lj_nome_cliente",
        "cliente",
        "nome_cliente",
        "cod_cliente",
        "codigo_cliente",
    ],

    # Colunas de valor vencido
    valor_vencido=[
        "tit_vencidos_valor_corrigido",
        "tit_vencidos_valor_atual",
        "titulos_vencidos_valor_corrigido",
        "titulos_vencidos_valor_atual",
        "valor_vencido",
        "vencido",
    ],

    # Colunas de valor a vencer
    valor_a_vencer=[
        "titulos_a_vencer_valor_atual",
        "tit_a_vencer_valor_atual",
        "titulos_a_vencer_valor_corrigido",
        "valor_a_vencer",
        "a_vencer",
    ],

    # Colunas de valor unico (quando nao ha separacao vencido/a vencer)
    valor_unico=[
        "valor_corrigido",
        "valor_total",
        "valor",
        "saldo",
        "saldo_devedor",
    ],

    # Colunas de data de vencimento
    data_vencimento=[
        "vencto_real",
        "venctoreal",
        "vencto_titulo",
        "venctotitulo",
        "vencto_orig",
        "vencimento_real",
        "vencimento_titulo",
        "vencimento_orig",
        "data_vencimento",
        "vencimento",
        "dt_vencimento",
    ],

    # Colunas de data de emissao
    data_emissao=[
        "data_de_emissao",
        "data_emissao",
        "dt_emissao",
        "emissao",
    ],

    # Colunas de numero do documento
    numero_documento=[
        "prf_numero",
        "prf_num",
        "numero_titulo",
        "num_titulo",
        "numero_documento",
        "documento",
    ],

    # Colunas de parcela
    parcela=[
        "parcela",
        "num_parcela",
        "parcela_num",
    ],

    # Colunas de tipo do titulo (TP)
    tipo_titulo=[
        "tp",
        "tipo",
        "tipo_titulo",
        "tipo_documento",
        "tipo_doc",
        "tipo_tit",
    ],

    # Substrings para busca flexivel de valor vencido
    substrings_vencido=[
        ["tit", "vencidos", "valor", "corrigido"],
        ["tit", "venc", "valor", "corrig"],
        ["titulos", "vencidos", "valor"],
        ["valor", "vencido"],
    ],

    # Substrings para busca flexivel de valor a vencer
    substrings_a_vencer=[
        ["titulos", "a_vencer", "valor", "atual"],
        ["tit", "a_vencer", "valor", "atual"],
        ["titulos", "a_vencer", "valor"],
        ["valor", "a_vencer"],
    ],
)


# =============================================================================
# PROCESSADOR DE CONTAS A RECEBER
# =============================================================================

class ProcessadorContasReceber(ProcessadorFinanceiroBase):
    """
    Processador especializado para planilhas de Contas a Receber.

    Herda da classe base e implementa especificidades de contas a receber:
    - Prefixo "C" para codigos de cliente
    - Mapeamento de colunas especifico para recebiveis

    Exemplo de uso:
        >>> processador = ProcessadorContasReceber()
        >>> df = processador.normalizar(planilha_excel)
        >>> print(df.columns)
        ['codigo', 'cliente', 'valor', 'dias_vencidos', 'TIPO']
    """

    def __init__(self):
        """Inicializa o processador com configuracao de Contas a Receber."""
        super().__init__(CONFIGURACAO_CONTAS_RECEBER)

    def get_tipo(self) -> TipoFinanceiro:
        """Retorna o tipo de processamento."""
        return TipoFinanceiro.CONTAS_RECEBER

    def get_prefixo_codigo(self) -> str:
        """Retorna o prefixo para codigos de cliente."""
        return "C"


# =============================================================================
# FUNCOES DE CONVENIENCIA (COMPATIBILIDADE COM CODIGO LEGADO)
# =============================================================================

_processador = None


def _get_processador() -> ProcessadorContasReceber:
    """Retorna instancia singleton do processador."""
    global _processador
    if _processador is None:
        _processador = ProcessadorContasReceber()
    return _processador


def normalizar_planilha_financeira(entrada: Any) -> pd.DataFrame:
    """
    Normaliza planilha de contas a receber e agrupa por codigo.

    Esta funcao mantem compatibilidade com o codigo legado.

    Args:
        entrada: DataFrame ou caminho para arquivo Excel

    Returns:
        DataFrame com colunas: codigo, cliente, valor, dias_vencidos, TIPO
    """
    return _get_processador().normalizar(entrada)


def normalizar_planilha_financeira_detalhada(entrada: Any) -> pd.DataFrame:
    """
    Normaliza planilha de contas a receber mantendo detalhes.

    Esta funcao mantem compatibilidade com o codigo legado.

    Args:
        entrada: DataFrame ou caminho para arquivo Excel

    Returns:
        DataFrame com registros detalhados
    """
    return _get_processador().normalizar_detalhado(entrada)
