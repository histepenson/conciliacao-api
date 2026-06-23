"""
Modulo de normalizacao de Balancete Contabil (importacao manual).

Layout esperado (planilha exportada do Protheus):
Conta, Descricao, Saldo anterior, Debito, Credito, Mov periodo, Saldo atual

- Conta: codigo com pontos (ex: 1.1.1.02.0001) -- normalizado para apenas digitos
  para casar com plano_contas.conta_contabil (ex: 111020001).
- Saldo anterior / Mov periodo / Saldo atual: numero BR com sufixo D (positivo) ou
  C (negativo). Linhas com saldo zerado vem em branco (NaN) -> tratado como 0.
- Debito / Credito: numero BR puro, sem sufixo (totais absolutos do periodo).
"""

import re
import unicodedata
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ["conta", "descricao", "saldo_anterior", "debito", "credito", "saldo_atual"]


def _remove_acentos(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", str(s))
        if unicodedata.category(c) != "Mn"
    )


def normalizar_nome_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza nomes de colunas: sem acento, minusculo, snake_case."""
    df = df.copy()
    df.columns = [_remove_acentos(col) for col in df.columns]
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[\r\n]+", "", regex=True)
        .str.replace(r"[^a-z0-9_]+", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    return df


def parse_numero_balancete(valor: Any) -> float:
    """
    Converte numero BR com sufixo D/C (ou sem sufixo) para float.

    D = positivo, C = negativo (mesma convencao de tools/banco/razao_banco.py).
    """
    if pd.isna(valor):
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    s = str(valor).strip()
    if not s:
        return 0.0

    s = s.replace(" ", "").replace(" ", "")
    s = s.replace("R$", "").replace("r$", "").strip()

    credito = False
    if s.upper().endswith("C"):
        credito = True
        s = s[:-1]
    elif s.upper().endswith("D"):
        s = s[:-1]

    s = re.sub(r"[^0-9,\.\-()]", "", s)
    if not s:
        return 0.0

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

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
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


def normalizar_codigo_conta(valor: Any) -> str:
    """Remove tudo que nao for digito do codigo da conta (ex: '1.1.1.02.0001' -> '111020001')."""
    if pd.isna(valor):
        return ""
    return re.sub(r"\D", "", str(valor))


def obter_coluna(df: pd.DataFrame, possiveis: list) -> str | None:
    for col in possiveis:
        if col in df.columns:
            return col
    for col in possiveis:
        for df_col in df.columns:
            if col in df_col:
                return df_col
    return None


def normalizar_balancete(entrada: Any) -> pd.DataFrame:
    """
    Normaliza planilha de Balancete Contabil.

    Args:
        entrada: DataFrame ja carregado (com header na primeira linha)

    Returns:
        DataFrame com colunas: conta_raw, conta_normalizada, descricao,
        saldo_anterior, debito, credito, mov_periodo, saldo_atual
    """
    if isinstance(entrada, pd.DataFrame):
        df = entrada.copy()
    else:
        raise ValueError("entrada deve ser um DataFrame")

    df = normalizar_nome_colunas(df)

    col_conta = obter_coluna(df, ["conta"])
    col_descricao = obter_coluna(df, ["descricao"])
    col_saldo_anterior = obter_coluna(df, ["saldo_anterior"])
    col_debito = obter_coluna(df, ["debito"])
    col_credito = obter_coluna(df, ["credito"])
    col_mov_periodo = obter_coluna(df, ["mov_periodo", "movperiodo", "mov_periodo_"])
    col_saldo_atual = obter_coluna(df, ["saldo_atual"])

    if not col_conta:
        raise ValueError(f"Coluna 'Conta' nao encontrada. Colunas: {list(df.columns)}")
    if not col_saldo_atual:
        raise ValueError(f"Coluna 'Saldo atual' nao encontrada. Colunas: {list(df.columns)}")

    df_norm = pd.DataFrame()
    df_norm["conta_raw"] = df[col_conta].astype(str).str.strip()
    df_norm["conta_normalizada"] = df_norm["conta_raw"].apply(normalizar_codigo_conta)
    df_norm["descricao"] = df[col_descricao].astype(str).str.strip() if col_descricao else ""

    df_norm["saldo_anterior"] = df[col_saldo_anterior].apply(parse_numero_balancete) if col_saldo_anterior else 0.0
    df_norm["debito"] = df[col_debito].apply(parse_numero_balancete) if col_debito else 0.0
    df_norm["credito"] = df[col_credito].apply(parse_numero_balancete) if col_credito else 0.0
    df_norm["mov_periodo"] = df[col_mov_periodo].apply(parse_numero_balancete) if col_mov_periodo else 0.0
    df_norm["saldo_atual"] = df[col_saldo_atual].apply(parse_numero_balancete)

    # Remove linhas sem codigo de conta valido (ex: linhas de totalizacao)
    df_norm = df_norm[df_norm["conta_normalizada"].str.len() > 0].copy()
    df_norm = df_norm.drop_duplicates(subset=["conta_normalizada"], keep="last").reset_index(drop=True)

    return df_norm
