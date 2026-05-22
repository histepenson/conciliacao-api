"""
Factory para selecao de processador financeiro.

Este modulo fornece uma interface unificada para obter o processador
apropriado baseado no tipo de operacao financeira (receber/pagar).
"""

import logging
from typing import Any, Dict, Type

import pandas as pd

from .base import ProcessadorFinanceiroBase, TipoFinanceiro, ResultadoValidacaoLayout
from .contas_receber import ProcessadorContasReceber
from .contas_pagar import ProcessadorContasPagar

logger = logging.getLogger(__name__)


# =============================================================================
# REGISTRY DE PROCESSADORES
# =============================================================================

_PROCESSADORES: Dict[TipoFinanceiro, Type[ProcessadorFinanceiroBase]] = {
    TipoFinanceiro.CONTAS_RECEBER: ProcessadorContasReceber,
    TipoFinanceiro.CONTAS_PAGAR: ProcessadorContasPagar,
}

# Cache de instancias (singleton por tipo)
_instancias: Dict[TipoFinanceiro, ProcessadorFinanceiroBase] = {}


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def get_processador(tipo: TipoFinanceiro) -> ProcessadorFinanceiroBase:
    """
    Obtem o processador apropriado para o tipo financeiro.

    Utiliza padrao singleton para reutilizar instancias.

    Args:
        tipo: Tipo de processamento (CONTAS_RECEBER ou CONTAS_PAGAR)

    Returns:
        Instancia do processador apropriado

    Raises:
        ValueError: Se o tipo nao for suportado
    """
    if tipo not in _PROCESSADORES:
        tipos_validos = [t.value for t in TipoFinanceiro]
        raise ValueError(
            f"Tipo de processamento nao suportado: {tipo}. "
            f"Tipos validos: {tipos_validos}"
        )

    if tipo not in _instancias:
        _instancias[tipo] = _PROCESSADORES[tipo]()
        logger.info(f"Criado processador para: {tipo.value}")

    return _instancias[tipo]


def get_processador_por_nome(nome: str) -> ProcessadorFinanceiroBase:
    """
    Obtem o processador pelo nome string do tipo.

    Args:
        nome: Nome do tipo ('contas_receber' ou 'contas_pagar')

    Returns:
        Instancia do processador apropriado

    Raises:
        ValueError: Se o nome nao corresponder a um tipo valido
    """
    try:
        tipo = TipoFinanceiro(nome.lower())
        return get_processador(tipo)
    except ValueError:
        tipos_validos = [t.value for t in TipoFinanceiro]
        raise ValueError(
            f"Tipo de processamento nao reconhecido: '{nome}'. "
            f"Tipos validos: {tipos_validos}"
        )


def registrar_processador(
    tipo: TipoFinanceiro,
    classe_processador: Type[ProcessadorFinanceiroBase]
) -> None:
    """
    Registra um novo tipo de processador.

    Permite extensao do sistema com novos tipos de processamento.

    Args:
        tipo: Tipo de processamento
        classe_processador: Classe do processador
    """
    _PROCESSADORES[tipo] = classe_processador
    # Limpa cache se ja existia instancia
    if tipo in _instancias:
        del _instancias[tipo]
    logger.info(f"Registrado processador para: {tipo.value}")


def listar_tipos_disponiveis() -> list[str]:
    """
    Lista todos os tipos de processamento disponiveis.

    Returns:
        Lista de nomes dos tipos disponiveis
    """
    return [t.value for t in _PROCESSADORES.keys()]


# =============================================================================
# FUNCOES DE CONVENIENCIA
# =============================================================================

def normalizar_planilha(
    entrada: Any,
    tipo: TipoFinanceiro | str
) -> pd.DataFrame:
    """
    Normaliza planilha financeira usando o processador apropriado.

    Funcao de conveniencia que seleciona automaticamente o processador.

    Args:
        entrada: DataFrame ou caminho para arquivo Excel
        tipo: Tipo de processamento (enum ou string)

    Returns:
        DataFrame normalizado e agrupado

    Exemplo:
        >>> df = normalizar_planilha(dados_excel, "contas_receber")
        >>> df = normalizar_planilha(dados_excel, TipoFinanceiro.CONTAS_PAGAR)
    """
    if isinstance(tipo, str):
        processador = get_processador_por_nome(tipo)
    else:
        processador = get_processador(tipo)

    return processador.normalizar(entrada)


def normalizar_planilha_detalhada(
    entrada: Any,
    tipo: TipoFinanceiro | str
) -> pd.DataFrame:
    """
    Normaliza planilha financeira mantendo detalhes por registro.

    Args:
        entrada: DataFrame ou caminho para arquivo Excel
        tipo: Tipo de processamento (enum ou string)

    Returns:
        DataFrame detalhado (nao agrupado)
    """
    if isinstance(tipo, str):
        processador = get_processador_por_nome(tipo)
    else:
        processador = get_processador(tipo)

    return processador.normalizar_detalhado(entrada)


def validar_layout_planilha(
    entrada: Any,
    tipo: TipoFinanceiro | str
) -> ResultadoValidacaoLayout:
    """
    Valida o layout de uma planilha financeira.

    Verifica se o arquivo possui as colunas esperadas antes de processar.

    Args:
        entrada: DataFrame ou caminho para arquivo Excel
        tipo: Tipo de processamento (enum ou string)

    Returns:
        ResultadoValidacaoLayout com detalhes da validacao

    Exemplo:
        >>> resultado = validar_layout_planilha(dados_excel, "contas_pagar")
        >>> if not resultado.valido:
        ...     print(f"Erro: {resultado.mensagem}")
    """
    if isinstance(tipo, str):
        processador = get_processador_por_nome(tipo)
    else:
        processador = get_processador(tipo)

    return processador.validar_layout(entrada)
