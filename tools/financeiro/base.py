"""
Módulo base com utilitários compartilhados para processamento financeiro.

Este módulo contém funções de uso comum entre Contas a Receber e Contas a Pagar:
- Normalização de colunas
- Parse de números em formato brasileiro
- Extração de códigos de cliente/fornecedor
- Busca flexível de colunas
"""

import pandas as pd
import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Tuple, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS E TIPOS
# =============================================================================

class TipoFinanceiro(str, Enum):
    """Tipos de processamento financeiro disponíveis."""
    CONTAS_RECEBER = "contas_receber"
    CONTAS_PAGAR = "contas_pagar"


class TipoPrazo(str, Enum):
    """Classificação por prazo de vencimento."""
    CURTO_PRAZO = "CURTO PRAZO"
    LONGO_PRAZO = "LONGO PRAZO"


@dataclass
class ConfiguracaoColunas:
    """Configuração de mapeamento de colunas para cada tipo de planilha."""
    # Colunas de identificação
    codigo_cliente: List[str]

    # Colunas de valor
    valor_vencido: List[str]
    valor_a_vencer: List[str]
    valor_unico: List[str]

    # Colunas de data
    data_vencimento: List[str]
    data_emissao: List[str]

    # Colunas auxiliares
    numero_documento: List[str]
    parcela: List[str]

    # Substrings para busca flexível de valor vencido
    substrings_vencido: List[List[str]]

    # Substrings para busca flexível de valor a vencer
    substrings_a_vencer: List[List[str]]


@dataclass
class ResultadoValidacaoLayout:
    """Resultado da validação do layout do arquivo."""
    valido: bool
    mensagem: str
    colunas_encontradas: List[str]
    colunas_faltando: List[str]
    colunas_arquivo: List[str]
    avisos: List[str]


# =============================================================================
# FUNÇÕES DE NORMALIZAÇÃO DE COLUNAS
# =============================================================================

def normalizar_nome_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza os nomes das colunas de um DataFrame.

    Transformações aplicadas:
    - Converte para minúsculas
    - Remove quebras de linha
    - Substitui caracteres especiais por underscore
    - Remove underscores duplicados e nas extremidades

    Args:
        df: DataFrame com colunas a normalizar

    Returns:
        DataFrame com colunas normalizadas
    """
    df = df.copy()
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[\r\n]+", "", regex=True)
        .str.replace(r"[^a-z0-9_]+", "_", regex=True)
        .str.replace(" ", "_")
        .str.replace("-", "_")
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    return df


def obter_coluna(df: pd.DataFrame, possiveis: List[str]) -> str:
    """
    Busca a primeira coluna existente de uma lista de possibilidades.

    Args:
        df: DataFrame onde buscar
        possiveis: Lista de nomes de colunas possíveis, em ordem de prioridade

    Returns:
        Nome da primeira coluna encontrada

    Raises:
        ValueError: Se nenhuma coluna for encontrada
    """
    for col in possiveis:
        if col in df.columns:
            return col
    raise ValueError(
        f"Nenhuma das colunas esperadas foi encontrada. "
        f"Esperadas: {possiveis} | Encontradas: {list(df.columns)}"
    )


def obter_coluna_opcional(df: pd.DataFrame, possiveis: List[str]) -> Optional[str]:
    """
    Busca a primeira coluna existente de uma lista, sem erro se não encontrar.

    Args:
        df: DataFrame onde buscar
        possiveis: Lista de nomes de colunas possíveis

    Returns:
        Nome da coluna encontrada ou None
    """
    for col in possiveis:
        if col in df.columns:
            return col
    return None


def encontrar_coluna_por_substrings(
    df: pd.DataFrame,
    substrings: List[str]
) -> Optional[str]:
    """
    Encontra uma coluna que contém todas as substrings especificadas.

    Args:
        df: DataFrame onde buscar
        substrings: Lista de substrings que devem estar presentes no nome da coluna

    Returns:
        Nome da coluna encontrada ou None
    """
    for col in df.columns:
        if all(sub in col for sub in substrings):
            return col
    return None


def buscar_coluna_flexivel(
    df: pd.DataFrame,
    lista_substrings: List[List[str]]
) -> Optional[str]:
    """
    Tenta encontrar uma coluna usando múltiplas combinações de substrings.

    Args:
        df: DataFrame onde buscar
        lista_substrings: Lista de listas de substrings para tentar em ordem

    Returns:
        Nome da primeira coluna encontrada ou None
    """
    for substrings in lista_substrings:
        col = encontrar_coluna_por_substrings(df, substrings)
        if col:
            return col
    return None


# =============================================================================
# FUNÇÕES DE PARSE DE NÚMEROS
# =============================================================================

def parse_numero_brasileiro(valor: Any) -> float:
    """
    Converte números em formato brasileiro para float.

    Formatos suportados:
    - 1.234.567,89 (BR com milhar)
    - 1234,89 (BR sem milhar)
    - (1.234,89) (negativo por parênteses)
    - 1234,89- (negativo por sufixo)
    - 1000D / 1000C (débito/crédito)

    Args:
        valor: Valor a converter (pode ser string, int, float ou None)

    Returns:
        Valor numérico como float (NaN se não puder converter)
    """
    if pd.isna(valor):
        return float("nan")

    if isinstance(valor, (int, float)):
        return float(valor)

    s = str(valor).strip()
    if not s:
        return float("nan")

    # Remover espaços e símbolos comuns
    s = s.replace("\u00a0", "").replace(" ", "")

    # Detectar sufixo D/C (Débito/Crédito)
    credito = False
    if s.upper().endswith("C"):
        credito = True
        s = s[:-1]
    elif s.upper().endswith("D"):
        s = s[:-1]

    # Remover caracteres não numéricos (exceto , . - ())
    s = re.sub(r"[^0-9,\.\-()]", "", s)

    # Detectar negativo por parênteses ou sufixo
    negativo = False
    if s.startswith("(") and s.endswith(")"):
        negativo = True
        s = s[1:-1]
    if s.endswith("-"):
        negativo = True
        s = s[:-1]

    # Converter formato BR para padrão
    if "," in s:
        # Formato BR: 1.234.567,89
        s = s.replace(".", "").replace(",", ".")
    else:
        # Sem vírgula: pode ser decimal com ponto ou milhar com vários pontos
        if s.count(".") > 1:
            s = s.replace(".", "")

    try:
        valor_float = float(s)
        if negativo or credito:
            valor_float = -valor_float
        return valor_float
    except Exception:
        return float("nan")


def serie_para_numerico(df: pd.DataFrame, coluna: str) -> pd.Series:
    """
    Converte uma coluna do DataFrame para valores numéricos.

    Args:
        df: DataFrame de origem
        coluna: Nome da coluna a converter

    Returns:
        Series com valores numéricos
    """
    return df[coluna].apply(parse_numero_brasileiro)


# =============================================================================
# FUNÇÕES DE EXTRAÇÃO DE CÓDIGO
# =============================================================================

def extrair_base_loja(texto: str) -> Tuple[str, str]:
    """
    Extrai código base e loja de um texto usando o separador '-'.

    Suporta qualquer quantidade de dígitos em base e loja.

    Formatos suportados:
    - "01704361-81-NOME CLIENTE" → ("01704361", "81")
    - "123456-789"               → ("123456", "789")
    - "123456-87"                → ("123456", "87")
    - "12345678" (sem separador) → ("12345678", "")

    Args:
        texto: Texto contendo o código

    Returns:
        Tupla (base, loja) extraídos pelo separador '-'
    """
    texto = str(texto or "").strip()
    if not texto:
        return "", ""

    partes = texto.split("-")
    base = re.sub(r"[^a-zA-Z0-9]", "", partes[0])

    if not base:
        return "", ""

    loja = ""
    if len(partes) >= 2:
        loja = re.sub(r"\D+", "", partes[1])

    return base, loja


def formatar_codigo(base: str, loja: str, prefixo: str = "C") -> str:
    """
    Formata código no padrão do sistema.

    Args:
        base: Código base (tamanho variável)
        loja: Código loja (tamanho variável)
        prefixo: Prefixo do código (default: "C" para cliente)

    Returns:
        Código formatado (ex: "C0170436181")
    """
    return f"{prefixo}{base}{loja}"


def normalizar_codigo_cliente(serie_cliente: pd.Series, prefixo: str = "C") -> pd.DataFrame:
    """
    Normaliza uma série de códigos de cliente/fornecedor.

    Processa códigos no formato "BASE-LOJA-NOME" usando o separador '-'.
    Suporta qualquer quantidade de dígitos em base e loja.

    Args:
        serie_cliente: Series com os valores originais
        prefixo: Prefixo para o código (C=cliente, F=fornecedor)

    Returns:
        DataFrame com colunas 'codigo' e 'cliente'
    """
    serie_cliente = serie_cliente.astype(str).str.strip()

    # Separar por hífen (formato: BASE-LOJA-NOME)
    partes = serie_cliente.str.split("-", n=2, expand=True)

    base_split = partes[0] if 0 in partes.columns else serie_cliente
    loja_split = partes[1] if 1 in partes.columns else pd.Series("", index=serie_cliente.index)

    # Extrair base (preserva letras + dígitos) e loja (apenas dígitos)
    base_clean = base_split.astype(str).str.replace(r"[^a-zA-Z0-9]", "", regex=True)
    loja_digits = loja_split.astype(str).str.extract(r"(\d+)", expand=False).fillna("")

    # Quando não tem separador '-', loja fica vazia (todos os dígitos são o código)
    loja_digits = loja_digits.where(loja_digits.str.len() > 0, "")

    # Formatar código final
    codigo = prefixo + base_clean + loja_digits

    # Extrair nome do cliente
    cliente_split = partes[2] if 2 in partes.columns else None
    if cliente_split is not None:
        cliente = cliente_split.fillna(serie_cliente).astype(str).str.strip()
    else:
        cliente = serie_cliente

    return pd.DataFrame({"codigo": codigo, "cliente": cliente})


# =============================================================================
# FUNÇÕES DE CLASSIFICAÇÃO
# =============================================================================

def classificar_prazo(dias_vencidos: int, limite_curto_prazo: int = 365) -> str:
    """
    Classifica o prazo baseado nos dias vencidos.

    Args:
        dias_vencidos: Número de dias vencidos
        limite_curto_prazo: Limite em dias para curto prazo (default: 365)

    Returns:
        TipoPrazo.CURTO_PRAZO ou TipoPrazo.LONGO_PRAZO
    """
    if pd.isna(dias_vencidos) or dias_vencidos <= limite_curto_prazo:
        return TipoPrazo.CURTO_PRAZO.value
    return TipoPrazo.LONGO_PRAZO.value


def calcular_dias_vencidos(data_vencimento: pd.Series, data_referencia: datetime = None) -> pd.Series:
    """
    Calcula dias vencidos a partir da data de vencimento.

    Args:
        data_vencimento: Series com datas de vencimento
        data_referencia: Data de referência (default: hoje)

    Returns:
        Series com dias vencidos
    """
    if data_referencia is None:
        data_referencia = datetime.now()

    data_venc = pd.to_datetime(data_vencimento, errors="coerce")
    return (data_referencia - data_venc).dt.days


# =============================================================================
# CLASSE BASE ABSTRATA PARA PROCESSADORES
# =============================================================================

class ProcessadorFinanceiroBase(ABC):
    """
    Classe base abstrata para processadores de planilhas financeiras.

    Define a interface comum para Contas a Receber e Contas a Pagar.
    """

    def __init__(self, config: ConfiguracaoColunas):
        """
        Inicializa o processador com configuração de colunas.

        Args:
            config: Configuração de mapeamento de colunas
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_tipo(self) -> TipoFinanceiro:
        """Retorna o tipo de processamento (receber/pagar)."""
        pass

    @abstractmethod
    def get_prefixo_codigo(self) -> str:
        """Retorna o prefixo para códigos (C=cliente, F=fornecedor)."""
        pass

    def carregar_dados(self, entrada: Any) -> pd.DataFrame:
        """
        Carrega dados de entrada (DataFrame ou arquivo Excel).

        Args:
            entrada: DataFrame ou caminho para arquivo Excel

        Returns:
            DataFrame carregado
        """
        if isinstance(entrada, pd.DataFrame):
            df = entrada.copy()
        else:
            df = pd.read_excel(entrada)

        self.logger.info(f"Total de registros lidos: {len(df)}")
        return df

    def normalizar_base(self, entrada: Any) -> pd.DataFrame:
        """
        Executa normalização base comum a todos os tipos.

        Args:
            entrada: DataFrame ou caminho para arquivo

        Returns:
            DataFrame normalizado com colunas padrão
        """
        df = self.carregar_dados(entrada)
        df = normalizar_nome_colunas(df)

        # Encontrar coluna de código/cliente
        col_cliente = obter_coluna(df, self.config.codigo_cliente)

        # Calcular valor
        df = self._calcular_valor(df)

        # Normalizar código
        codigo_df = normalizar_codigo_cliente(
            df[col_cliente],
            prefixo=self.get_prefixo_codigo()
        )
        df["codigo"] = codigo_df["codigo"]
        df["cliente"] = codigo_df["cliente"]

        # Processar datas
        df = self._processar_datas(df)

        # Processar campos auxiliares
        df = self._processar_campos_auxiliares(df)

        # Limpar registros sem valor
        df = df[df["valor"].notna()].copy()

        return df

    def _calcular_valor(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula o valor total (vencido + a vencer ou valor único).

        Args:
            df: DataFrame com dados

        Returns:
            DataFrame com coluna 'valor' adicionada
        """
        # Tentar encontrar colunas exatas primeiro
        col_vencido = obter_coluna_opcional(df, self.config.valor_vencido)
        col_a_vencer = obter_coluna_opcional(df, self.config.valor_a_vencer)

        # Se não encontrou, tentar busca flexível
        if not col_vencido:
            col_vencido = buscar_coluna_flexivel(df, self.config.substrings_vencido)

        if not col_a_vencer:
            col_a_vencer = buscar_coluna_flexivel(df, self.config.substrings_a_vencer)

        # Se temos ambas colunas, somar
        if col_vencido and col_a_vencer:
            self.logger.info(f"Valor será calculado por soma: {col_vencido} + {col_a_vencer}")
            serie_vencido = serie_para_numerico(df, col_vencido).fillna(0.0)
            serie_a_vencer = serie_para_numerico(df, col_a_vencer).fillna(0.0)
            df["valor"] = serie_vencido + serie_a_vencer
            self.logger.info(
                f"Soma vencido: {serie_vencido.sum():.2f} | "
                f"Soma a vencer: {serie_a_vencer.sum():.2f} | "
                f"Total: {df['valor'].sum():.2f}"
            )
        else:
            # Usar coluna única de valor
            col_valor = obter_coluna_opcional(df, self.config.valor_unico)
            if not col_valor:
                col_valor = next((c for c in df.columns if "valor" in c), None)

            if not col_valor:
                raise ValueError(
                    f"Nenhuma coluna de valor encontrada. Colunas: {list(df.columns)}"
                )

            self.logger.info(f"Valor será lido diretamente da coluna: {col_valor}")
            df["valor"] = serie_para_numerico(df, col_valor)

        return df

    def _processar_datas(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processa colunas de data e calcula dias vencidos.

        Args:
            df: DataFrame com dados

        Returns:
            DataFrame com colunas de data processadas
        """
        # Data de vencimento
        col_vencimento = obter_coluna(df, self.config.data_vencimento)
        df["data_vencimento"] = pd.to_datetime(df[col_vencimento], errors="coerce")

        # Data de emissão (opcional)
        col_emissao = obter_coluna_opcional(df, self.config.data_emissao)
        if not col_emissao:
            col_emissao = buscar_coluna_flexivel(df, [
                ["data", "emissao"],
                ["data", "de", "emissao"],
                ["dt", "emissao"],
            ])

        if col_emissao:
            df["data_emissao"] = df[col_emissao]
        else:
            df["data_emissao"] = pd.NaT

        # Calcular dias vencidos
        df["dias_vencidos"] = calcular_dias_vencidos(df["data_vencimento"])

        return df

    def _processar_campos_auxiliares(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Processa campos auxiliares (número documento, parcela).

        Args:
            df: DataFrame com dados

        Returns:
            DataFrame com campos auxiliares
        """
        # Número do documento
        col_doc = obter_coluna_opcional(df, self.config.numero_documento)
        if not col_doc:
            col_doc = buscar_coluna_flexivel(df, [
                ["prf", "numero"],
                ["prf", "num"],
                ["numero", "documento"],
                ["num", "doc"],
            ])
        df["numero_documento"] = df[col_doc] if col_doc else None

        # Parcela
        col_parcela = obter_coluna_opcional(df, self.config.parcela)
        df["parcela"] = df[col_parcela] if col_parcela else None

        return df

    def validar_layout(self, entrada: Any) -> ResultadoValidacaoLayout:
        """
        Valida se o arquivo possui o layout esperado.

        Verifica se as colunas obrigatórias estão presentes no arquivo
        antes de iniciar o processamento.

        Args:
            entrada: DataFrame ou caminho para arquivo

        Returns:
            ResultadoValidacaoLayout com detalhes da validação
        """
        df = self.carregar_dados(entrada)
        df = normalizar_nome_colunas(df)

        colunas_arquivo = list(df.columns)
        colunas_encontradas = []
        colunas_faltando = []
        avisos = []

        # 1. Verificar coluna de código/cliente (OBRIGATÓRIA)
        col_cliente = obter_coluna_opcional(df, self.config.codigo_cliente)
        if col_cliente:
            colunas_encontradas.append(f"Código/Cliente: {col_cliente}")
        else:
            colunas_faltando.append("Código do Cliente/Fornecedor")

        # 2. Verificar colunas de valor (pelo menos uma forma de obter valor)
        col_vencido = obter_coluna_opcional(df, self.config.valor_vencido)
        col_a_vencer = obter_coluna_opcional(df, self.config.valor_a_vencer)
        col_valor_unico = obter_coluna_opcional(df, self.config.valor_unico)

        # Busca flexível
        if not col_vencido:
            col_vencido = buscar_coluna_flexivel(df, self.config.substrings_vencido)
        if not col_a_vencer:
            col_a_vencer = buscar_coluna_flexivel(df, self.config.substrings_a_vencer)

        tem_valor_duplo = col_vencido and col_a_vencer
        tem_valor_unico = col_valor_unico is not None

        if tem_valor_duplo:
            colunas_encontradas.append(f"Valor Vencido: {col_vencido}")
            colunas_encontradas.append(f"Valor a Vencer: {col_a_vencer}")
        elif tem_valor_unico:
            colunas_encontradas.append(f"Valor: {col_valor_unico}")
        elif col_vencido:
            colunas_encontradas.append(f"Valor Vencido: {col_vencido}")
            avisos.append("Coluna de valor a vencer não encontrada - usando apenas valor vencido")
        elif col_a_vencer:
            colunas_encontradas.append(f"Valor a Vencer: {col_a_vencer}")
            avisos.append("Coluna de valor vencido não encontrada - usando apenas valor a vencer")
        else:
            colunas_faltando.append("Valor (vencido/a vencer ou valor único)")

        # 3. Verificar data de vencimento (OBRIGATÓRIA)
        col_vencimento = obter_coluna_opcional(df, self.config.data_vencimento)
        if col_vencimento:
            colunas_encontradas.append(f"Data Vencimento: {col_vencimento}")
        else:
            colunas_faltando.append("Data de Vencimento")

        # 4. Verificar data de emissão (opcional - apenas aviso)
        col_emissao = obter_coluna_opcional(df, self.config.data_emissao)
        if col_emissao:
            colunas_encontradas.append(f"Data Emissão: {col_emissao}")
        else:
            avisos.append("Coluna de data de emissão não encontrada (opcional)")

        # 5. Verificar número do documento (opcional - apenas aviso)
        col_doc = obter_coluna_opcional(df, self.config.numero_documento)
        if col_doc:
            colunas_encontradas.append(f"Número Documento: {col_doc}")
        else:
            avisos.append("Coluna de número do documento não encontrada (opcional)")

        # Determinar resultado
        valido = len(colunas_faltando) == 0

        if valido:
            mensagem = f"Layout válido. {len(colunas_encontradas)} colunas mapeadas corretamente."
        else:
            mensagem = (
                f"Layout inválido! Colunas obrigatórias não encontradas: {', '.join(colunas_faltando)}. "
                f"Verifique se o arquivo possui o formato esperado para {self.get_tipo().value}."
            )

        self.logger.info(f"Validação de layout: {'VÁLIDO' if valido else 'INVÁLIDO'}")
        self.logger.info(f"Colunas encontradas: {colunas_encontradas}")
        if colunas_faltando:
            self.logger.warning(f"Colunas faltando: {colunas_faltando}")
        if avisos:
            self.logger.info(f"Avisos: {avisos}")

        return ResultadoValidacaoLayout(
            valido=valido,
            mensagem=mensagem,
            colunas_encontradas=colunas_encontradas,
            colunas_faltando=colunas_faltando,
            colunas_arquivo=colunas_arquivo,
            avisos=avisos
        )

    def normalizar(self, entrada: Any) -> pd.DataFrame:
        """
        Normaliza planilha e agrupa por código.

        Args:
            entrada: DataFrame ou caminho para arquivo

        Returns:
            DataFrame agrupado com colunas: codigo, cliente, valor, dias_vencidos, TIPO
        """
        df = self.normalizar_base(entrada)

        # Agrupar por código
        df_agrupado = (
            df.groupby("codigo", as_index=False)
            .agg(
                cliente=("cliente", "first"),
                valor=("valor", "sum"),
                dias_vencidos=("dias_vencidos", "max"),
            )
        )

        # Classificar prazo
        df_agrupado["TIPO"] = df_agrupado["dias_vencidos"].apply(classificar_prazo)

        self.logger.info(
            f"{self.get_tipo().value} normalizado: {df_agrupado['codigo'].nunique()} códigos | "
            f"total valor: {df_agrupado['valor'].sum():.2f}"
        )

        return df_agrupado

    def normalizar_detalhado(self, entrada: Any) -> pd.DataFrame:
        """
        Normaliza planilha mantendo detalhes por registro.

        Args:
            entrada: DataFrame ou caminho para arquivo

        Returns:
            DataFrame com todos os registros detalhados
        """
        df = self.normalizar_base(entrada)
        return df[[
            "codigo", "cliente", "valor",
            "data_emissao", "data_vencimento",
            "numero_documento", "parcela"
        ]].copy()
