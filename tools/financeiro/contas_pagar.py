"""
Modulo de processamento de Contas a Pagar.

Processa planilhas de contas a pagar (fornecedores) extraindo:
- Codigo do fornecedor (formato F{base}{loja})
- Nome do fornecedor
- Valor total (vencido + a vencer)
- Dias vencidos
- Classificacao de prazo

Layout esperado do relatorio:
Codigo-Nome do Fornecedor, Prf-Numero Parcela, Tp, Natureza, Data de Emissao,
Data de Vencto, Vencto Real, Valor Original, Tit Vencidos Valor nominal,
Tit Vencidos Valor corrigido, Titulos a vencer Valor nominal, Portador,
Vlr.juros ou permanencia, Dias Atraso, Historico(Vencidos+Vencer)
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
# CONFIGURACAO DE COLUNAS PARA CONTAS A PAGAR
# =============================================================================

CONFIGURACAO_CONTAS_PAGAR = ConfiguracaoColunas(
    # Colunas de identificacao do fornecedor
    # Layout: "Codigo-Nome do Fornecedor" -> normalizado: "codigo_nome_do_fornecedor"
    codigo_cliente=[
        # Formato do relatorio real
        "codigo_nome_do_fornecedor",
        "codigo_nome_fornecedor",
        # Variacoes com hifen/underscore
        "codigo_lj_nome_do_fornecedor",
        "codigo_lj_nome_fornecedor",
        # Outras variacoes
        "cod_fornecedor",
        "codigo_fornecedor",
        "fornecedor",
        "nome_fornecedor",
        "credor",
        "cod_credor",
        "codigo_credor",
        "nome_credor",
    ],

    # Colunas de valor vencido
    # Layout: "Tit Vencidos Valor corrigido" -> normalizado: "tit_vencidos_valor_corrigido"
    valor_vencido=[
        # Formato do relatorio real
        "tit_vencidos_valor_corrigido",
        "tit_vencidos_valor_nominal",
        # Variacoes
        "titulos_vencidos_valor_corrigido",
        "titulos_vencidos_valor_nominal",
        "titulos_vencidos_valor_atual",
        "valor_vencido",
        "vencido",
    ],

    # Colunas de valor a vencer
    # Layout: "Titulos a vencer Valor nominal" -> normalizado: "titulos_a_vencer_valor_nominal"
    valor_a_vencer=[
        # Formato do relatorio real
        "titulos_a_vencer_valor_nominal",
        "titulos_a_vencer_valor_atual",
        "titulos_a_vencer_valor_corrigido",
        # Variacoes
        "tit_a_vencer_valor_nominal",
        "tit_a_vencer_valor_atual",
        "valor_a_vencer",
        "a_vencer",
    ],

    # Colunas de valor unico (quando nao ha separacao vencido/a vencer)
    # Layout: "Valor Original" -> normalizado: "valor_original"
    valor_unico=[
        "valor_original",
        "valor_corrigido",
        "valor_total",
        "valor",
        "saldo",
        "saldo_a_pagar",
        "saldo_devedor",
        "valor_liquido",
    ],

    # Colunas de data de vencimento
    # Layout: "Vencto Real" -> normalizado: "vencto_real"
    # Layout: "Data de Vencto" -> normalizado: "data_de_vencto"
    data_vencimento=[
        # Formato do relatorio real
        "vencto_real",
        "data_de_vencto",
        # Variacoes
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
    # Layout: "Data de Emissao" -> normalizado: "data_de_emissao"
    data_emissao=[
        # Formato do relatorio real
        "data_de_emissao",
        # Variacoes
        "data_emissao",
        "dt_emissao",
        "emissao",
        "data_entrada",
        "dt_entrada",
        "data_nf",
    ],

    # Colunas de numero do documento
    # Layout: "Prf-Numero Parcela" -> normalizado: "prf_numero_parcela"
    numero_documento=[
        # Formato do relatorio real
        "prf_numero_parcela",
        "prf_numero",
        # Variacoes
        "prf_num",
        "numero_titulo",
        "num_titulo",
        "numero_documento",
        "documento",
        "numero_nf",
        "nf_numero",
        "nota_fiscal",
        "nf",
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
        ["tit", "vencidos", "valor", "nominal"],
        ["tit", "venc", "valor", "corrig"],
        ["titulos", "vencidos", "valor"],
        ["valor", "vencido"],
    ],

    # Substrings para busca flexivel de valor a vencer
    substrings_a_vencer=[
        ["titulos", "a_vencer", "valor", "nominal"],
        ["titulos", "a_vencer", "valor", "atual"],
        ["tit", "a_vencer", "valor"],
        ["valor", "a_vencer"],
    ],
)


# =============================================================================
# PROCESSADOR DE CONTAS A PAGAR
# =============================================================================

class ProcessadorContasPagar(ProcessadorFinanceiroBase):
    """
    Processador especializado para planilhas de Contas a Pagar.

    Herda da classe base e implementa especificidades de contas a pagar:
    - Prefixo "F" para codigos de fornecedor
    - Mapeamento de colunas especifico para pagaveis

    Layout esperado:
        Codigo-Nome do Fornecedor, Prf-Numero Parcela, Tp, Natureza,
        Data de Emissao, Data de Vencto, Vencto Real, Valor Original,
        Tit Vencidos Valor nominal, Tit Vencidos Valor corrigido,
        Titulos a vencer Valor nominal, Portador, Vlr.juros ou permanencia,
        Dias Atraso, Historico(Vencidos+Vencer)

    Exemplo de uso:
        >>> processador = ProcessadorContasPagar()
        >>> df = processador.normalizar(planilha_excel)
        >>> print(df.columns)
        ['codigo', 'cliente', 'valor', 'dias_vencidos', 'TIPO']

    Nota: O campo 'cliente' contem o nome do fornecedor para manter
    compatibilidade com a estrutura existente do sistema.
    """

    def __init__(self):
        """Inicializa o processador com configuracao de Contas a Pagar."""
        super().__init__(CONFIGURACAO_CONTAS_PAGAR)

    def get_tipo(self) -> TipoFinanceiro:
        """Retorna o tipo de processamento."""
        return TipoFinanceiro.CONTAS_PAGAR

    def get_prefixo_codigo(self) -> str:
        """Retorna o prefixo para codigos de fornecedor."""
        return "F"


# =============================================================================
# FUNCOES DE CONVENIENCIA
# =============================================================================

_processador = None


def _get_processador() -> ProcessadorContasPagar:
    """Retorna instancia singleton do processador."""
    global _processador
    if _processador is None:
        _processador = ProcessadorContasPagar()
    return _processador


def normalizar_planilha_contas_pagar(entrada: Any) -> pd.DataFrame:
    """
    Normaliza planilha de contas a pagar e agrupa por codigo.

    Args:
        entrada: DataFrame ou caminho para arquivo Excel

    Returns:
        DataFrame com colunas: codigo, cliente, valor, dias_vencidos, TIPO

    Nota: O campo 'cliente' contem o nome do fornecedor.
    """
    return _get_processador().normalizar(entrada)


def normalizar_planilha_contas_pagar_detalhada(entrada: Any) -> pd.DataFrame:
    """
    Normaliza planilha de contas a pagar mantendo detalhes.

    Args:
        entrada: DataFrame ou caminho para arquivo Excel

    Returns:
        DataFrame com registros detalhados
    """
    return _get_processador().normalizar_detalhado(entrada)
