import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def obter_coluna(df: pd.DataFrame, possiveis: list[str]) -> str:
    """
    Retorna a primeira coluna existente no DataFrame a partir de uma lista.
    """
    for col in possiveis:
        if col in df.columns:
            return col
    raise ValueError(
        f"Nenhuma das colunas esperadas foi encontrada. "
        f"Esperadas: {possiveis} | Encontradas: {list(df.columns)}"
    )


def normalizar_planilha_financeira(entrada):
    """
    Normaliza a planilha financeira com fallback de colunas.
    Retorna DataFrame agrupado por codigo do cliente.
    """

    # ==========================
    # 1️⃣ CARREGAR DATAFRAME
    # ==========================
    if isinstance(entrada, pd.DataFrame):
        df = entrada.copy()
    else:
        df = pd.read_excel(entrada)

    logger.info(f"Total de registros lidos: {len(df)}")

    # ==========================
    # 2️⃣ NORMALIZAR NOMES DAS COLUNAS
    # ==========================
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    # ==========================
    # 3️⃣ FALLBACK DE COLUNAS
    # ==========================
    col_cliente = obter_coluna(df, [
        "codigo_lj_nome_do_cliente",
        "cliente",
        "nome_cliente"
    ])

    col_valor = obter_coluna(df, [
        "tit_vencidos_valor_corrigido",
        "valor_corrigido",
        "valor"
    ])

    col_vencimento = obter_coluna(df, [
        "vencto_real",
        "data_vencimento",
        "vencimento"
    ])

    # ==========================
    # 4️⃣ NORMALIZAR CLIENTE E CÓDIGO
    # ==========================
    # Exemplo esperado: 000672-01-A A DANTAS RIBEIRO
    partes = df[col_cliente].astype(str).str.split("-", n=2, expand=True)

    codigo_base = partes[0].str.zfill(6)
    loja = partes[1].str.zfill(2)
    df["codigo"] = "C" + codigo_base + loja

    df["cliente"] = partes[2].str.strip()

    # ==========================
    # 5️⃣ NORMALIZAR VALOR
    # ==========================
    df["valor"] = (
        df[col_valor]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    # ==========================
    # 6️⃣ NORMALIZAR DATA / DIAS VENCIDOS
    # ==========================
    df["data_vencimento"] = pd.to_datetime(
        df[col_vencimento], errors="coerce"
    )

    hoje = datetime.now()
    df["dias_vencidos"] = (hoje - df["data_vencimento"]).dt.days

    # ==========================
    # 7️⃣ LIMPEZA
    # ==========================
    df = df[df["valor"].notna()].copy()

    # ==========================
    # 8️⃣ AGRUPAMENTO FINAL (POR CÓDIGO)
    # ==========================
    df_agrupado = (
        df
        .groupby("codigo", as_index=False)
        .agg(
            cliente=("cliente", "first"),
            valor=("valor", "sum"),
            dias_vencidos=("dias_vencidos", "max")
        )
    )

    # ==========================
    # 9️⃣ TIPO (CURTO / LONGO PRAZO)
    # ==========================
    df_agrupado["TIPO"] = df_agrupado["dias_vencidos"].apply(
        lambda x: "LONGO PRAZO" if pd.notna(x) and x > 365 else "CURTO PRAZO"
    )

    return df_agrupado
