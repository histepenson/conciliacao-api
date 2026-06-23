"""
Modulo de normalizacao de Razao Contabil de Banco (CTBR400).

Processa planilha de razao contabil extraindo:
- Data do lancamento
- Lote/Documento
- Historico (com extracao de documento)
- Debito e Credito

Layout esperado CTBR400:
DATA,LOTE/SUB/DOC/LINHA,HISTORICO,XPARTIDA,C CUSTO,ITEM CONTA,
COD CL VAL,DEBITO,CREDITO,SALDO ATUAL

Extracao de documentos do HISTORICO:
- CFOP: 5101 NF 000034619 - FAZENDAO IND.
- COMP. NF9/000034395-FAZENDAO
- CFOP: 6501 NF 000003941 - DASSOLER AGRO
"""

import pandas as pd
import re
import logging
from typing import Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


# =============================================================================
# FUNCOES DE NORMALIZACAO
# =============================================================================

def normalizar_nome_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza os nomes das colunas de um DataFrame."""
    import unicodedata
    df = df.copy()

    # Primeiro, remover acentos
    def remove_acentos(s):
        return ''.join(
            c for c in unicodedata.normalize('NFD', str(s))
            if unicodedata.category(c) != 'Mn'
        )

    df.columns = [remove_acentos(col) for col in df.columns]

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


def parse_numero_brasileiro(valor: Any) -> float:
    """Converte numeros em formato brasileiro para float."""
    if pd.isna(valor):
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    s = str(valor).strip()
    if not s:
        return 0.0

    # Remover espacos e simbolos comuns
    s = s.replace("\u00a0", "").replace(" ", "")

    # Remover R$ e outros prefixos de moeda
    s = s.replace("R$", "").replace("r$", "").strip()

    # Detectar sufixo D/C
    credito = False
    if s.upper().endswith("C"):
        credito = True
        s = s[:-1]
    elif s.upper().endswith("D"):
        s = s[:-1]

    # Remover caracteres nao numericos (exceto , . - ())
    s = re.sub(r"[^0-9,\.\-()]", "", s)

    if not s:
        return 0.0

    # Detectar negativo
    negativo = False
    if s.startswith("(") and s.endswith(")"):
        negativo = True
        s = s[1:-1]
    if s.endswith("-"):
        negativo = True
        s = s[:-1]
    if s.startswith("-"):
        negativo = True
        s = s[1:]

    # Converter formato BR para formato internacional
    # Detectar se e formato brasileiro (1.234,56) ou internacional (1,234.56)
    if "," in s and "." in s:
        # Se a virgula vem depois do ponto, e formato BR
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            # Formato internacional
            s = s.replace(",", "")
    elif "," in s:
        # Apenas virgula - formato BR (1234,56)
        s = s.replace(",", ".")
    elif s.count(".") > 1:
            s = s.replace(".", "")

    try:
        valor_float = float(s)
        if negativo or credito:
            valor_float = -valor_float
        return valor_float
    except Exception:
        return 0.0


def extrair_documento_historico(historico: str) -> Tuple[str, str, str]:
    """
    Extrai prefixo e numero de documento do campo HISTORICO.

    Padroes reconhecidos:
    - CFOP: 5101 NF 000034619 - FAZENDAO IND.
    - COMP. NF9/000034395-FAZENDAO
    - CFOP: 6501 NF 000003941 - DASSOLER AGRO
    - NF 12345
    - RA 01120253
    - BOL 501819069

    Returns:
        Tupla (documento_extraido, prefixo, numero)
    """
    if pd.isna(historico) or not str(historico).strip():
        return "", "", ""

    texto = str(historico).strip().upper()

    # Padrao especial: BOL NF501816337 / BOL501816337
    match = re.search(r'\bBOL\s*(?:NF)?\s*(\d+)', texto)
    if match:
        numero_raw = match.group(1)
        numero = re.sub(r"^0+", "", numero_raw) or "0"
        documento = f"BOL {numero_raw}"
        return documento, "BOL", numero

    # Lista de prefixos conhecidos
    prefixos_conhecidos = [
        "NF9", "NF", "RA", "PA", "DV", "FT", "BOL", "DUP", "FAT",
        "REC", "PAG", "DEP", "TED", "DOC", "PIX", "CHQ", "CHEQUE"
    ]

    # Tentar encontrar padrao: PREFIXO + NUMERO
    for prefixo in prefixos_conhecidos:
        # Padrao: PREFIXO 000034619 ou PREFIXO/000034619 ou PREFIXO-000034619
        pattern = rf'\b{prefixo}[\s/\-]*(\d+)'
        match = re.search(pattern, texto)
        if match:
            numero_raw = match.group(1)
            # Remover zeros a esquerda
            numero = re.sub(r"^0+", "", numero_raw) or "0"
            documento = f"{prefixo} {numero_raw}"
            return documento, prefixo, numero

    # Tentar padrao generico: qualquer sequencia de letras seguida de numeros
    match = re.search(r'\b([A-Z]{2,4})[\s/\-]*(\d{4,})', texto)
    if match:
        prefixo = match.group(1)
        numero_raw = match.group(2)
        numero = re.sub(r"^0+", "", numero_raw) or "0"
        documento = f"{prefixo} {numero_raw}"
        return documento, prefixo, numero

    return "", "", ""


def formatar_data(data: Any) -> str:
    """Formata data para string padrao DD/MM/YYYY."""
    from datetime import datetime, timedelta

    if pd.isna(data):
        return ""

    # Atalho: ja esta no formato final (ex: vem assim de cargas MATR900/CTBR400
    # importadas manualmente) -- evita chamar pd.to_datetime() escalar por linha,
    # que e' extremamente lento quando aplicado em milhares de linhas (cada
    # chamada individual tem overhead de parsing significativo).
    if isinstance(data, str) and re.fullmatch(r"\d{2}/\d{2}/\d{4}", data.strip()):
        return data.strip()

    try:
        # Se for numero (serial do Excel), converter
        if isinstance(data, (int, float)):
            # Excel usa epoch 30/12/1899
            # Numeros grandes (> 1000) sao provavelmente serial do Excel
            if data > 1000:
                base_excel = datetime(1899, 12, 30)
                data_dt = base_excel + timedelta(days=int(data))
                return data_dt.strftime("%d/%m/%Y")
            else:
                return str(int(data))

        if isinstance(data, str):
            # Verificar se e numero em formato string
            try:
                num = float(data)
                if num > 1000:
                    base_excel = datetime(1899, 12, 30)
                    data_dt = base_excel + timedelta(days=int(num))
                    return data_dt.strftime("%d/%m/%Y")
            except ValueError:
                pass

            data_dt = pd.to_datetime(data, dayfirst=True, errors="coerce")
            if pd.isna(data_dt):
                return str(data).strip()
            return data_dt.strftime("%d/%m/%Y")
        else:
            data_dt = pd.to_datetime(data, errors="coerce")
            if pd.isna(data_dt):
                return str(data).strip()
            return data_dt.strftime("%d/%m/%Y")
    except Exception:
        return str(data).strip()


def obter_coluna(df: pd.DataFrame, possiveis: list) -> Optional[str]:
    """Busca a primeira coluna existente de uma lista de possibilidades."""
    for col in possiveis:
        if col in df.columns:
            return col
    # Tentar busca parcial (substring)
    for col in possiveis:
        for df_col in df.columns:
            if col in df_col:
                return df_col
    return None


def normalizar_coluna_acentos(nome: str) -> str:
    """Remove acentos de uma string para comparacao."""
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFD', nome)
        if unicodedata.category(c) != 'Mn'
    )


def encontrar_coluna_por_substring(df: pd.DataFrame, substrings: List[str]) -> Optional[str]:
    """Encontra coluna que contem todas as substrings."""
    for col in df.columns:
        if all(sub in col for sub in substrings):
            return col
    return None


# =============================================================================
# FUNCAO PRINCIPAL
# =============================================================================

def normalizar_razao_banco(entrada: Any) -> pd.DataFrame:
    """
    Normaliza relatorio de Razao Contabil de Banco (CTBR400).

    Layout esperado:
    DATA,LOTE/SUB/DOC/LINHA,HISTORICO,XPARTIDA,C CUSTO,ITEM CONTA,
    COD CL VAL,DEBITO,CREDITO,SALDO ATUAL

    Retorna DataFrame com colunas:
    - data: Data do lancamento
    - lote_doc: Lote/Sub/Doc/Linha original
    - historico: Historico do lancamento
    - documento_extraido: Documento extraido do historico
    - prefixo: Prefixo do documento (NF, RA, etc)
    - numero: Numero do documento sem zeros
    - chave_documento: Chave normalizada (PREFIXO_NUMERO)
    - debito: Valor de debito
    - credito: Valor de credito
    - valor: Valor (positivo=debito, negativo=credito)
    - tipo: DEBITO ou CREDITO
    - saldo_atual: Saldo apos lancamento

    Args:
        entrada: DataFrame ou caminho para arquivo Excel

    Returns:
        DataFrame normalizado com lancamentos do razao
    """
    logger.info("[RAZAO BANCO] Iniciando normalizacao")

    # ==========================
    # 1. CARREGAR DATAFRAME
    # ==========================
    if isinstance(entrada, pd.DataFrame):
        df = entrada.copy()
    elif isinstance(entrada, str):
        df = pd.read_excel(entrada)
    else:
        raise ValueError("entrada deve ser DataFrame ou caminho de arquivo")

    logger.info(f"[RAZAO BANCO] Registros lidos: {len(df)}")
    logger.info(f"[RAZAO BANCO] Colunas originais: {list(df.columns)}")

    # ==========================
    # 2. NORMALIZAR COLUNAS
    # ==========================
    df = normalizar_nome_colunas(df)
    logger.info(f"[RAZAO BANCO] Colunas normalizadas: {list(df.columns)}")

    # ==========================
    # 3. MAPEAR COLUNAS
    # ==========================
    col_data = obter_coluna(df, ["data", "dt", "data_lancamento", "data_lanc"])
    col_lote_doc = obter_coluna(df, ["lote_sub_doc_linha", "lote", "documento", "doc"])

    # Historico pode ter varios nomes
    col_historico = obter_coluna(df, ["historico", "hist", "descricao"])

    # Debito e credito
    col_debito = obter_coluna(df, ["debito", "deb", "valor_debito"])
    col_credito = obter_coluna(df, ["credito", "cred", "valor_credito"])

    # Saldo
    col_saldo = obter_coluna(df, ["saldo_atual", "saldo", "saldo_final"])

    # Log das colunas encontradas
    logger.info(f"[RAZAO BANCO] Coluna DATA: {col_data}")
    logger.info(f"[RAZAO BANCO] Coluna HISTORICO: {col_historico}")
    logger.info(f"[RAZAO BANCO] Coluna DEBITO: {col_debito}")
    logger.info(f"[RAZAO BANCO] Coluna CREDITO: {col_credito}")

    # Debug: mostrar valores brutos das colunas de valores
    if col_debito:
        logger.info(f"[RAZAO BANCO] Tipos na coluna DEBITO: {df[col_debito].apply(type).value_counts().to_dict()}")
        logger.info(f"[RAZAO BANCO] Valores brutos DEBITO (10 primeiros): {df[col_debito].head(10).tolist()}")
    if col_credito:
        logger.info(f"[RAZAO BANCO] Tipos na coluna CREDITO: {df[col_credito].apply(type).value_counts().to_dict()}")
        logger.info(f"[RAZAO BANCO] Valores brutos CREDITO (10 primeiros): {df[col_credito].head(10).tolist()}")

    # Validar colunas obrigatorias
    if not col_data:
        raise ValueError(f"Coluna de DATA nao encontrada. Colunas: {list(df.columns)}")
    if not col_historico:
        raise ValueError(f"Coluna de HISTORICO nao encontrada. Colunas: {list(df.columns)}")
    if not col_debito and not col_credito:
        raise ValueError(f"Colunas de DEBITO/CREDITO nao encontradas. Colunas: {list(df.columns)}")

    # ==========================
    # 4. PROCESSAR DADOS
    # ==========================
    df_norm = pd.DataFrame()

    # Data
    df_norm["data"] = df[col_data].apply(formatar_data)

    # Lote/Documento original
    if col_lote_doc:
        df_norm["lote_doc"] = df[col_lote_doc].astype(str).str.strip()
    else:
        df_norm["lote_doc"] = ""

    # Historico
    df_norm["historico"] = df[col_historico].astype(str).str.strip()

    # Extrair documento do historico
    doc_extraido = df_norm["historico"].apply(extrair_documento_historico)
    df_norm["documento_extraido"] = doc_extraido.apply(lambda x: x[0])
    df_norm["prefixo"] = doc_extraido.apply(lambda x: x[1])
    df_norm["numero"] = doc_extraido.apply(lambda x: x[2])

    # Chave de documento normalizada para matching
    df_norm["chave_documento"] = df_norm["prefixo"] + "_" + df_norm["numero"]

    # Valores de debito e credito
    if col_debito:
        # Log amostra dos valores originais
        amostra_deb = df[col_debito].head(5).tolist()
        logger.info(f"[RAZAO BANCO] Amostra DEBITO original: {amostra_deb}")
        df_norm["debito"] = df[col_debito].apply(parse_numero_brasileiro).abs()
        logger.info(f"[RAZAO BANCO] Amostra DEBITO convertido: {df_norm['debito'].head(5).tolist()}")
    else:
        df_norm["debito"] = 0.0

    if col_credito:
        # Log amostra dos valores originais
        amostra_cred = df[col_credito].head(5).tolist()
        logger.info(f"[RAZAO BANCO] Amostra CREDITO original: {amostra_cred}")
        df_norm["credito"] = df[col_credito].apply(parse_numero_brasileiro).abs()
        logger.info(f"[RAZAO BANCO] Amostra CREDITO convertido: {df_norm['credito'].head(5).tolist()}")
    else:
        df_norm["credito"] = 0.0

    # Valor liquido
    # Regra contabil para conta ATIVO (Banco):
    # - Debito = aumento (entrada de dinheiro)
    # - Credito = diminuicao (saida de dinheiro)
    # Para matching com extrato:
    # - Debito no razao = Entrada no extrato (valor positivo)
    # - Credito no razao = Saida no extrato (valor negativo)
    df_norm["valor"] = df_norm["debito"] - df_norm["credito"]

    # Tipo de lancamento
    df_norm["tipo"] = "DEBITO"
    df_norm.loc[df_norm["credito"] > 0, "tipo"] = "CREDITO"

    # Saldo atual
    if col_saldo:
        df_norm["saldo_atual"] = df[col_saldo].apply(parse_numero_brasileiro)
    else:
        df_norm["saldo_atual"] = 0.0

    # ==========================
    # 5. LIMPAR REGISTROS
    # ==========================
    # Remover registros sem movimento
    df_norm = df_norm[(df_norm["debito"] != 0) | (df_norm["credito"] != 0)].copy()

    # Registros sem documento extraido podem ser mantidos para analise
    # mas marcamos com chave especial
    mask_sem_doc = df_norm["chave_documento"] == "_"
    if mask_sem_doc.any():
        df_norm.loc[mask_sem_doc, "chave_documento"] = ["SEM_DOC_" + str(i) for i in df_norm.loc[mask_sem_doc].index]

    logger.info(f"[RAZAO BANCO] Lancamentos normalizados: {len(df_norm)}")
    logger.info(f"[RAZAO BANCO] Total debitos: {df_norm['debito'].sum():,.2f}")
    logger.info(f"[RAZAO BANCO] Total creditos: {df_norm['credito'].sum():,.2f}")
    logger.info(f"[RAZAO BANCO] Documentos extraidos: {(df_norm['prefixo'] != '').sum()}")

    return df_norm
