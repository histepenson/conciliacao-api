"""
Pacote de processamento financeiro.

Este pacote contem modulos para normalizacao de planilhas financeiras:
- Contas a Receber (clientes)
- Contas a Pagar (fornecedores)

Uso basico:
    >>> from tools.financeiro import normalizar_planilha, TipoFinanceiro
    >>>
    >>> # Contas a Receber
    >>> df_receber = normalizar_planilha(dados, TipoFinanceiro.CONTAS_RECEBER)
    >>>
    >>> # Contas a Pagar
    >>> df_pagar = normalizar_planilha(dados, TipoFinanceiro.CONTAS_PAGAR)

Para compatibilidade com codigo legado:
    >>> from tools.financeiro import normalizar_planilha_financeira
    >>> df = normalizar_planilha_financeira(dados)  # Contas a Receber
"""

# Tipos e enums
from .base import (
    TipoFinanceiro,
    TipoPrazo,
    ConfiguracaoColunas,
    ProcessadorFinanceiroBase,
    ResultadoValidacaoLayout,
)

# Processadores especificos
from .contas_receber import (
    ProcessadorContasReceber,
    normalizar_planilha_financeira,
    normalizar_planilha_financeira_detalhada,
)

from .contas_pagar import (
    ProcessadorContasPagar,
    normalizar_planilha_contas_pagar,
    normalizar_planilha_contas_pagar_detalhada,
)

# Factory
from .factory import (
    get_processador,
    get_processador_por_nome,
    registrar_processador,
    listar_tipos_disponiveis,
    normalizar_planilha,
    normalizar_planilha_detalhada,
    validar_layout_planilha,
)

# Utilitarios base (para uso avancado)
from .base import (
    normalizar_nome_colunas,
    obter_coluna,
    obter_coluna_opcional,
    encontrar_coluna_por_substrings,
    parse_numero_brasileiro,
    serie_para_numerico,
    extrair_base_loja,
    formatar_codigo,
    normalizar_codigo_cliente,
    classificar_prazo,
    calcular_dias_vencidos,
)


__all__ = [
    # Tipos
    "TipoFinanceiro",
    "TipoPrazo",
    "ConfiguracaoColunas",
    "ProcessadorFinanceiroBase",
    "ResultadoValidacaoLayout",

    # Processadores
    "ProcessadorContasReceber",
    "ProcessadorContasPagar",

    # Funcoes Contas a Receber
    "normalizar_planilha_financeira",
    "normalizar_planilha_financeira_detalhada",

    # Funcoes Contas a Pagar
    "normalizar_planilha_contas_pagar",
    "normalizar_planilha_contas_pagar_detalhada",

    # Factory
    "get_processador",
    "get_processador_por_nome",
    "registrar_processador",
    "listar_tipos_disponiveis",
    "normalizar_planilha",
    "normalizar_planilha_detalhada",
    "validar_layout_planilha",

    # Utilitarios
    "normalizar_nome_colunas",
    "obter_coluna",
    "obter_coluna_opcional",
    "encontrar_coluna_por_substrings",
    "parse_numero_brasileiro",
    "serie_para_numerico",
    "extrair_base_loja",
    "formatar_codigo",
    "normalizar_codigo_cliente",
    "classificar_prazo",
    "calcular_dias_vencidos",
]
