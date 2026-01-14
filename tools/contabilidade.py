import pandas as pd
import re


def normalizar_planilha_contabilidade(entrada):
    """
    Normaliza relatório de CONTABILIDADE (Balancete).

    Layout esperado:
    Codigo | Descricao | ... | Saldo atual

    Retorna:
    codigo | cliente | valor
    """

    # ==========================
    # 1️⃣ CARREGAR DATAFRAME
    # ==========================
    if isinstance(entrada, pd.DataFrame):
        df = entrada.copy()
    elif isinstance(entrada, str):
        df = pd.read_excel(entrada)
    else:
        raise ValueError("entrada deve ser DataFrame ou caminho de arquivo")

    # ==========================
    # 2️⃣ MAPEAR COLUNAS (DIRETO)
    # ==========================
    col_codigo = None
    col_cliente = None
    col_valor = None

    for col in df.columns:
        if col.lower().startswith("codigo"):
            col_codigo = col
        if col.lower().startswith("descricao"):
            col_cliente = col
        if col.lower() == "saldo atual":
            col_valor = col

    if not col_codigo or not col_valor:
        raise ValueError(
            f"Layout contábil inválido. Colunas encontradas: {list(df.columns)}"
        )

    # ==========================
    # 3️⃣ NORMALIZAR
    # ==========================
    df_norm = pd.DataFrame()
    df_norm["codigo"] = df[col_codigo]
    df_norm["cliente"] = df[col_cliente] if col_cliente else None

    # ==========================
    # 4️⃣ CONVERTER VALOR
    # ==========================
    def converter_valor(v):
        if pd.isna(v):
            return 0.0
        v = str(v).replace(".", "").replace(",", ".")
        try:
            return float(v)
        except:
            return 0.0

    df_norm["valor"] = df[col_valor].apply(converter_valor)

    # ==========================
    # 5️⃣ LIMPAR E AGRUPAR
    # ==========================
    df_norm = df_norm[df_norm["codigo"].notna()].copy()

    df_agrupado = (
        df_norm
        .groupby(["codigo", "cliente"], dropna=False)
        .agg({"valor": "sum"})
        .reset_index()
    )

    return df_agrupado
