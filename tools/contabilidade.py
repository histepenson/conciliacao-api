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
    # 2️⃣ MAPEAR COLUNAS (FLEXÍVEL)
    # ==========================
    def normalizar_nome(col: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower()).strip("_")

    colunas_norm = [(col, normalizar_nome(col)) for col in df.columns]

    codigo_cols = [col for col, norm in colunas_norm if norm.startswith("codigo")]
    descricao_cols = [col for col, norm in colunas_norm if norm.startswith("descricao")]
    saldo_cols = [
        col
        for col, norm in colunas_norm
        if norm == "saldo_atual" or norm.startswith("saldo_atual")
    ]

    # Quando há duplicidade de Codigo/Descricao, a primeira costuma ser a conta contábil.
    col_codigo = codigo_cols[1] if len(codigo_cols) > 1 else (codigo_cols[0] if codigo_cols else None)
    col_cliente = descricao_cols[1] if len(descricao_cols) > 1 else (descricao_cols[0] if descricao_cols else None)
    col_valor = saldo_cols[0] if saldo_cols else None

    if not col_codigo or not col_valor:
        raise ValueError(
            f"Layout contábil inválido. Colunas encontradas: {list(df.columns)}"
        )

    # ==========================
    # 3️⃣ NORMALIZAR
    # ==========================
    df_norm = pd.DataFrame()
    df_norm["codigo_raw"] = df[col_codigo]
    df_norm["cliente"] = df[col_cliente] if col_cliente else None

    # ==========================
    # 4️⃣ CÓDIGO (JÁ VEM FORMATADO DA CONTABILIDADE)
    # ==========================
    df_norm["codigo"] = df_norm["codigo_raw"].astype(str).str.strip()
    df_norm = df_norm[df_norm["codigo"].str.len() > 0].copy()

    # ==========================
    # 5️⃣ CONVERTER VALOR
    # ==========================
    def converter_valor(v: object) -> float:
        if pd.isna(v):
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)

        s = str(v).strip()
        if not s:
            return 0.0

        negativo = False
        if s.startswith("(") and s.endswith(")"):
            negativo = True
            s = s[1:-1]
        if s.endswith("-"):
            negativo = True
            s = s[:-1]

        s_upper = s.upper()
        if s_upper.endswith("D") or s_upper.endswith("C"):
            sufixo = s_upper[-1]
            s = s[:-1]
            if sufixo == "C":
                negativo = True

        s = (
            s.replace("\u00a0", "")
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )

        try:
            valor = float(s)
            return -valor if negativo else valor
        except Exception:
            return 0.0

    df_norm["valor"] = df[col_valor].apply(converter_valor)

    # ==========================
    # 6️⃣ LIMPAR E AGRUPAR
    # ==========================
    df_norm = df_norm[df_norm["codigo"].astype(str).str.len() > 0].copy()

    # IMPORTANTE: agrupar apenas por codigo evita duplicação no merge por codigo
    df_agrupado = (
        df_norm.groupby(["codigo"], dropna=False, as_index=False)
        .agg(
            cliente=("cliente", "first"),
            valor=("valor", "sum"),
        )
    )

    return df_agrupado
