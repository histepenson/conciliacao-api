# services/estrategias/bbc/leasing_razao_contabil.py
"""
Parser exclusivo da BBC para o export de Razao Contabil usado na
Conferencia LEASING. Ao contrario dos relatorios "Movimentacao Diaria",
esse arquivo ja e' tabular (uma linha = um lancamento, header limpo na
primeira linha) -- nao precisa parsing de layout impresso.

Cada linha tem so' debito OU credito preenchido (a outra fica vazia); o
lado D/C fica implicito em qual coluna tem valor. "sHist" e' o texto de
historico que, na pratica, e' a chave usada para casar contra a
natureza da base unificada no motor de matching (Fase 5).
"""
import unicodedata
from typing import BinaryIO, Union

import pandas as pd

COLUNAS_RESULTADO = [
    "dt_lanc_contabil", "conta_contabil", "nome_conta_contabil",
    "historico_padrao", "historico", "conta_contra", "nome_conta_contra",
    "valor_debito", "valor_credito",
]


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return texto.strip().upper()


def _encontrar_coluna(df: pd.DataFrame, *candidatos: str) -> str:
    mapa = {_normalizar(c): c for c in df.columns}
    for candidato in candidatos:
        col = mapa.get(_normalizar(candidato))
        if col:
            return col
    raise ValueError(f"Nenhuma das colunas {candidatos} foi encontrada no razao. Colunas do arquivo: {list(df.columns)}")


def _texto_ou_none(serie: pd.Series) -> pd.Series:
    """Converte para string preservando None em vez de virar a string 'nan'."""
    return serie.apply(lambda v: None if pd.isna(v) else str(v).strip())


def parsear_razao_contabil(arquivo: Union[bytes, BinaryIO]) -> pd.DataFrame:
    """
    Le o export de Razao Contabil e retorna um DataFrame no formato
    COLUNAS_RESULTADO, uma linha por lancamento do razao.
    """
    df_raw = pd.read_excel(arquivo)

    col_data = _encontrar_coluna(df_raw, "dDtLancContabil")
    col_conta = _encontrar_coluna(df_raw, "sCodContaContabil")
    col_nome_conta = _encontrar_coluna(df_raw, "sNomeContaContabil")
    col_hist_padrao = _encontrar_coluna(df_raw, "sNomeHistPadrao")
    col_hist = _encontrar_coluna(df_raw, "sHist")
    col_conta_contra = _encontrar_coluna(df_raw, "sCodContaContra")
    col_nome_conta_contra = _encontrar_coluna(df_raw, "sNomeContaContra")
    col_debito = _encontrar_coluna(df_raw, "nTotalDebito")
    col_credito = _encontrar_coluna(df_raw, "nTotalCredito")

    # Descarta linhas sem conta contabil: sao rodape/totalizador do export
    # (subtotal geral), nao um lancamento de verdade -- mesmo tendo valor
    # em debito/credito, nao tem historico nem conta pra comparar.
    df_raw = df_raw[df_raw[col_conta].notna()]

    if df_raw.empty:
        raise ValueError("Nenhum lancamento com conta contabil foi encontrado no arquivo do razao.")

    resultado = pd.DataFrame({
        "dt_lanc_contabil": pd.to_datetime(df_raw[col_data], errors="coerce"),
        "conta_contabil": _texto_ou_none(df_raw[col_conta]),
        "nome_conta_contabil": _texto_ou_none(df_raw[col_nome_conta]),
        "historico_padrao": _texto_ou_none(df_raw[col_hist_padrao]),
        "historico": _texto_ou_none(df_raw[col_hist]),
        "conta_contra": _texto_ou_none(df_raw[col_conta_contra]),
        "nome_conta_contra": _texto_ou_none(df_raw[col_nome_conta_contra]),
        "valor_debito": pd.to_numeric(df_raw[col_debito], errors="coerce"),
        "valor_credito": pd.to_numeric(df_raw[col_credito], errors="coerce"),
    })

    # Descarta linhas sem debito nem credito (nao deveria acontecer, mas
    # protege contra linhas em branco no meio do export).
    resultado = resultado[resultado["valor_debito"].notna() | resultado["valor_credito"].notna()]

    if resultado.empty:
        raise ValueError("Nenhum lancamento com debito ou credito foi encontrado no arquivo do razao.")

    return resultado.reset_index(drop=True)
