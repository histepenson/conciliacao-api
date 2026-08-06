# services/estrategias/bbc/leasing_extrato_bradesco.py
"""
Parser exclusivo da BBC para o Extrato Bradesco usado na Conferencia
LEASING. Ao contrario dos relatorios "Movimentacao Diaria" (que ja tem
codigo de natureza no proprio arquivo), o extrato bancario nao tem
nenhuma coluna de natureza -- a classificacao e' inferida comparando a
coluna "Cliente Debitado" contra as regras cadastradas em
LeasingRegraClassificacao (match tipo "contem", case/acento-insensivel).

So' as linhas que baterem com alguma regra sao retornadas -- o extrato
inteiro tem centenas de lancamentos do banco sem relacao nenhuma com
LEASING, entao nao faz sentido importar tudo como "nao classificado"
(seria ruido). Isso segue exatamente o filtro que foi validado
manualmente antes de este modulo existir: nomes de cliente conhecidos
(assessorias) e o padrao "LEIL" (leilao).
"""
import unicodedata
from typing import BinaryIO, Iterable, List, Union

import pandas as pd

COLUNAS_RESULTADO = [
    "relatorio", "lcto", "dt_lanc", "dt_mov", "nr_operacao", "cliente",
    "natureza_codigo", "valor",
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
    raise ValueError(f"Nenhuma das colunas {candidatos} foi encontrada no extrato. Colunas do arquivo: {list(df.columns)}")


def parsear_extrato_bradesco(arquivo: Union[bytes, BinaryIO], regras: Iterable[dict]) -> pd.DataFrame:
    """
    Le o Extrato Bradesco e retorna um DataFrame so' com as linhas cujo
    "Cliente Debitado" bate com alguma regra de classificacao (contains,
    case/acento-insensivel), colunas: COLUNAS_RESULTADO.

    `regras` e' uma lista de dicts {"padrao_cliente": str, "natureza_codigo": str},
    tentadas na ordem, padrao mais longo primeiro (regra mais especifica
    ganha de uma regra generica curta).
    """
    df_raw = pd.read_excel(arquivo)

    col_data = _encontrar_coluna(df_raw, "Data Mensagem")
    col_nr_msg = _encontrar_coluna(df_raw, "Nr Msg")
    col_cliente = _encontrar_coluna(df_raw, "Cliente Debitado")
    col_valor = _encontrar_coluna(df_raw, "Valor")

    regras_ordenadas = sorted(
        (r for r in regras if r.get("padrao_cliente")),
        key=lambda r: len(r["padrao_cliente"]),
        reverse=True,
    )
    regras_norm = [(_normalizar(r["padrao_cliente"]), r["natureza_codigo"]) for r in regras_ordenadas]

    def _classificar(cliente) -> str:
        cliente_norm = _normalizar(cliente)
        if not cliente_norm:
            return None
        for padrao_norm, natureza_codigo in regras_norm:
            if padrao_norm in cliente_norm:
                return natureza_codigo
        return None

    df_raw = df_raw.copy()
    df_raw["_natureza_codigo"] = df_raw[col_cliente].apply(_classificar)
    df_classificado = df_raw[df_raw["_natureza_codigo"].notna()].copy()

    if df_classificado.empty:
        return pd.DataFrame(columns=COLUNAS_RESULTADO)

    nr_msg = pd.to_numeric(df_classificado[col_nr_msg], errors="coerce").astype("Int64").astype(str)

    resultado = pd.DataFrame({
        "relatorio": "Extrato Bradesco",
        "lcto": nr_msg,
        "dt_lanc": pd.to_datetime(df_classificado[col_data], errors="coerce"),
        "nr_operacao": nr_msg,
        "cliente": df_classificado[col_cliente].astype(str).str.strip(),
        "natureza_codigo": df_classificado["_natureza_codigo"],
        "valor": pd.to_numeric(df_classificado[col_valor], errors="coerce").fillna(0.0),
    })
    resultado["dt_mov"] = resultado["dt_lanc"]

    return resultado.reset_index(drop=True)
