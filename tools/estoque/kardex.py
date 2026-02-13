"""
Modulo de normalizacao de Kardex (Movimentacao de Estoque).

Processa planilha Kardex extraindo:
- Data da operacao (Operacao Data)
- Codigo fiscal (CF)
- Entradas Custo Total / Saidas Custo Total
- Classificacao de tipo de movimento

Colunas esperadas do Kardex:
Codigo;Descricao;UM;Tipo;Grupo;Custo Medio;Qtd Saldo;Vlr Total Saldo;
Posicao IPI;Endereco;Operacao Data;ARM;TES;CF;Documento Numero;
Entradas Quantidade;Entradas Custo Total;Custo Medio do Movimento;
Saidas Quantidade;Saidas Custo Total;Saldo Quantidade;Saldo Valor Total;
CLI/FOR/CC/PJ/OP/OS
"""

import pandas as pd
import logging
import re
from typing import Any

from tools.banco.razao_banco import (
    normalizar_nome_colunas,
    parse_numero_brasileiro,
    obter_coluna,
    formatar_data,
)

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES DE MAPEAMENTO DE MOVIMENTOS
# =============================================================================

# CFs que representam Entradas (Debito no Razao)
ENTRADAS_CFS = {"DE0", "DE1", "DE2", "DE3", "DE4", "DE5", "DE6", "DE7"}

# CFs que representam Saidas (Credito no Razao)
SAIDAS_CFS = {"RE0", "RE1", "RE2", "RE3", "RE4", "RE5", "RE6", "RE7"}

# CFs com grupo proprio
PR0_CFS = {"PR0"}

# CFOPs de devolucao de entrada -> agrupados como "DEV"
DEV_CFOPS = {
    "1201", "1202", "1410", "1411",
    "1949", "2201", "2202", "2410", "2411", "2949",
}

# CFOPs de devolucao de saida -> agrupados como "DEV"
DEV_CFOPS_SAIDA = {
    "5201", "5202", "5410", "5411",
    "6201", "6202", "6410", "6411",
}

# CFOPs de venda/CPV -> agrupados como "CPV" (separado de SAIDAS genericas)
CPV_CFOPS = {
    "5101", "5102", "5103", "5104", "5105", "5106", "5109", "5110",
    "5401", "5402", "5405", "5551", "5556", "5910", "5949",
    "6101", "6102", "6103", "6104", "6105", "6106", "6107", "6109", "6110", "6910", "6949",
    "6401", "6402", "6405", "6551", "6556",
}


def _normalizar_cf_para_classificacao(cf: Any) -> str:
    """
    Normaliza CF para classificacao usando apenas texto bruto.
    """
    if cf is None:
        return ""

    cf_upper = str(cf).strip().upper()
    if not cf_upper or cf_upper == "NAN":
        return ""

    return cf_upper


def _cf_lookup_key(cf_texto: str) -> str:
    """
    Chave de lookup para CFOP em listas explicitas (DEV/CPV).
    Mantem regra de lista, apenas tolerando formatacao de texto.
    """
    if not cf_texto:
        return ""

    texto = str(cf_texto).strip().upper()
    if not texto:
        return ""

    # Se for algo como 1201.0, converte para 1201
    try:
        n = float(texto.replace(",", "."))
        if n == int(n) and n > 0:
            numero = str(int(n))
            if len(numero) > 4 and numero[0] in "1234567":
                return numero[:4]
            return numero
    except (ValueError, OverflowError):
        pass

    # Mantem apenas digitos para comparacao de CFOP (ex.: 1.201 -> 1201)
    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return texto

    # Alguns layouts podem trazer sufixos decimais/zeros (ex.: 2.949,00 -> 294900).
    # Nesses casos, prioriza os 4 primeiros digitos como CFOP.
    if len(digitos) > 4 and digitos[0] in "1234567":
        return digitos[:4]

    return digitos


def classificar_movimento_kardex(cf: str) -> tuple:
    """
    Classifica um registro do Kardex pelo CF.

    Tudo e aglutinado em dois grupos:
    - CF em ENTRADAS_CFS (DE0-DE7, PR0) ou numerico < 5000 -> "ENTRADAS"
    - CF em SAIDAS_CFS (RE0-RE7) ou numerico >= 5000 -> "SAIDAS"

    Returns:
        Tupla (codigo_movimento, tipo, coluna_valor)
    """
    cf_upper = _normalizar_cf_para_classificacao(cf)

    if cf_upper in PR0_CFS:
        return "PR0", "ENTRADA", "entradas_custo_total"

    if cf_upper in ENTRADAS_CFS:
        return cf_upper, "ENTRADA", "entradas_custo_total"

    if cf_upper in SAIDAS_CFS:
        return cf_upper, "SAIDA", "saidas_custo_total"

    cf_lookup = _cf_lookup_key(cf_upper)

    # DEV/CPV seguem a mesma logica: match explicito por lista de CFOP
    if cf_lookup in DEV_CFOPS:
        # Devolucao: sempre usar coluna de saidas no Kardex (normalizada em positivo)
        return "DEV", "ENTRADA", "saidas_custo_total"
    if cf_lookup in DEV_CFOPS_SAIDA:
        # Devolucao: sempre usar coluna de saidas no Kardex (normalizada em positivo)
        return "DEV", "ENTRADA", "saidas_custo_total"
    if cf_lookup in CPV_CFOPS:
        return "CPV", "SAIDA", "saidas_custo_total"

    # Fallback para demais CFOPs numericos
    if cf_lookup.isdigit():
        cfop = int(cf_lookup)
        if cfop < 5000:
            return "ENTRADAS", "ENTRADA", "entradas_custo_total"
        else:
            return "SAIDAS", "SAIDA", "saidas_custo_total"

    # CF desconhecido
    return cf_upper, "DESCONHECIDO", None


def normalizar_kardex(entrada: Any) -> pd.DataFrame:
    """
    Normaliza relatorio Kardex de estoque.

    Retorna DataFrame com colunas:
    - data: Data da operacao (DD/MM/YYYY)
    - cf: CF original
    - codigo_movimento: CF agrupado (DE0-DE7, RE0-RE7, PR0, ENTRADAS, SAIDAS)
    - tipo_movimento: ENTRADA ou SAIDA
    - valor: Valor do custo (Entradas Custo Total ou Saidas Custo Total)
    - documento_numero: Numero do documento
    - descricao: Descricao do item
    """
    logger.info("[KARDEX] Iniciando normalizacao")

    # 1. CARREGAR DATAFRAME
    if isinstance(entrada, pd.DataFrame):
        df = entrada.copy()
    elif isinstance(entrada, str):
        df = pd.read_excel(entrada)
    else:
        raise ValueError("entrada deve ser DataFrame ou caminho de arquivo")

    logger.info(f"[KARDEX] Registros lidos: {len(df)}")
    logger.info(f"[KARDEX] Colunas originais: {list(df.columns)}")

    # 2. NORMALIZAR COLUNAS
    df = normalizar_nome_colunas(df)
    logger.info(f"[KARDEX] Colunas normalizadas: {list(df.columns)}")

    # 3. MAPEAR COLUNAS
    col_data = obter_coluna(df, ["operacao_data", "operacao", "data_operacao", "data"])
    col_cf = obter_coluna(df, ["cf", "c_f", "codigo_fiscal", "cfop"])
    col_entradas_custo = obter_coluna(df, [
        "entradas_custo_total", "entradas_custo", "custo_entrada", "entrada_custo_total"
    ])
    col_saidas_custo = obter_coluna(df, [
        "saidas_custo_total", "saidas_custo", "custo_saida", "saida_custo_total"
    ])
    col_documento = obter_coluna(df, ["documento_numero", "documento", "doc_numero"])
    col_descricao = obter_coluna(df, ["descricao", "desc"])
    col_codigo = obter_coluna(df, ["codigo", "cod"])

    logger.info(f"[KARDEX] Coluna DATA: {col_data}")
    logger.info(f"[KARDEX] Coluna CF: {col_cf}")
    logger.info(f"[KARDEX] Coluna ENTRADAS CUSTO: {col_entradas_custo}")
    logger.info(f"[KARDEX] Coluna SAIDAS CUSTO: {col_saidas_custo}")

    # Validar colunas obrigatorias
    if not col_data:
        raise ValueError(f"Coluna de DATA (Operacao Data) nao encontrada. Colunas: {list(df.columns)}")
    if not col_cf:
        raise ValueError(f"Coluna de CF nao encontrada. Colunas: {list(df.columns)}")
    if not col_entradas_custo and not col_saidas_custo:
        raise ValueError(f"Colunas de custo (Entradas/Saidas) nao encontradas. Colunas: {list(df.columns)}")

    # 4. PROCESSAR DADOS
    df_norm = pd.DataFrame()

    df_norm["data"] = df[col_data].apply(formatar_data)
    df_norm["cf"] = df[col_cf].apply(_normalizar_cf_para_classificacao)

    # Log dos CFs unicos para debug
    cfs_unicos = df_norm["cf"].unique().tolist()
    logger.info(f"[KARDEX] CFs unicos encontrados ({len(cfs_unicos)}): {cfs_unicos[:30]}")

    if col_entradas_custo:
        df_norm["entradas_custo_total"] = df[col_entradas_custo].apply(parse_numero_brasileiro).abs()
    else:
        df_norm["entradas_custo_total"] = 0.0

    if col_saidas_custo:
        df_norm["saidas_custo_total"] = df[col_saidas_custo].apply(parse_numero_brasileiro).abs()
    else:
        df_norm["saidas_custo_total"] = 0.0

    if col_documento:
        df_norm["documento_numero"] = df[col_documento].astype(str).str.strip()
    else:
        df_norm["documento_numero"] = ""

    if col_descricao:
        df_norm["descricao"] = df[col_descricao].astype(str).str.strip()
    else:
        df_norm["descricao"] = ""

    if col_codigo:
        df_norm["codigo_produto"] = df[col_codigo].astype(str).str.strip()
    else:
        df_norm["codigo_produto"] = ""

    # Classificar cada linha
    classificacao = df_norm["cf"].apply(classificar_movimento_kardex)
    df_norm["codigo_movimento"] = classificacao.apply(lambda x: x[0])
    df_norm["tipo_movimento"] = classificacao.apply(lambda x: x[1])
    col_valor_key = classificacao.apply(lambda x: x[2])

    # Extrair valor correto baseado na classificacao
    df_norm["valor"] = 0.0
    mask_entrada = col_valor_key == "entradas_custo_total"
    mask_saida = col_valor_key == "saidas_custo_total"
    df_norm.loc[mask_entrada, "valor"] = df_norm.loc[mask_entrada, "entradas_custo_total"]
    df_norm.loc[mask_saida, "valor"] = df_norm.loc[mask_saida, "saidas_custo_total"]

    # 5. LIMPAR - remover registros sem valor
    df_norm = df_norm[df_norm["valor"] != 0].copy()

    # Remover registros com data vazia
    df_norm = df_norm[df_norm["data"].str.strip() != ""].copy()

    # Remover desconhecidos
    df_norm = df_norm[df_norm["tipo_movimento"] != "DESCONHECIDO"].copy()

    logger.info(f"[KARDEX] Movimentos normalizados: {len(df_norm)}")
    logger.info(f"[KARDEX] Total entradas: {df_norm.loc[df_norm['tipo_movimento'] == 'ENTRADA', 'valor'].sum():,.2f}")
    logger.info(f"[KARDEX] Total saidas: {df_norm.loc[df_norm['tipo_movimento'] == 'SAIDA', 'valor'].sum():,.2f}")
    logger.info(f"[KARDEX] Codigos de movimento encontrados: {df_norm['codigo_movimento'].unique().tolist()}")
    logger.info(
        "[KARDEX] Quantidade por codigo_movimento: %s",
        df_norm["codigo_movimento"].value_counts().to_dict(),
    )
    logger.info(
        "[KARDEX] Total DEV (qtd=%s, valor=%s)",
        int((df_norm["codigo_movimento"] == "DEV").sum()),
        round(float(df_norm.loc[df_norm["codigo_movimento"] == "DEV", "valor"].sum()), 2),
    )

    return df_norm
