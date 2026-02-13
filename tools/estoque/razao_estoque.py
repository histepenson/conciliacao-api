"""
Modulo de normalizacao de Razao Contabil de Estoque (CTBR400).

Mesmo layout do Razao de Banco, mas com extracao diferente:
- Codigo de movimento: HISTORICO[:3] (DE7, CPV, DEV, RE0, etc)
  - CPV -> mapeado para "SAIDAS"
  - DEV -> mapeado para "ENTRADAS"
- Data da movimentacao: extraida do texto do HISTORICO (padrao "DATA: DD/MM/")
- Agrupa por (data_extraida, codigo_movimento)

Layout esperado CTBR400:
DATA,LOTE/SUB/DOC/LINHA,HISTORICO,XPARTIDA,C CUSTO,ITEM CONTA,
COD CL VAL,DEBITO,CREDITO,SALDO ATUAL
"""

import pandas as pd
import re
import logging
from typing import Any, Optional

from tools.banco.razao_banco import (
    normalizar_nome_colunas,
    parse_numero_brasileiro,
    obter_coluna,
    formatar_data,
)

logger = logging.getLogger(__name__)

# Mapeamento de codigos do Razao para codigos de agrupamento
# Todos os movimentos sao aglutinados em ENTRADAS ou SAIDAS
MAPEAMENTO_CODIGO_RAZAO = {
    "CPV": "CPV",
    "BON": "CPV",
    "DEV": "DEV",
    "DE0": "DE0",
    "DE1": "DE1",
    "DE2": "DE2",
    "DE3": "DE3",
    "DE4": "DE4",
    "DE5": "DE5",
    "DE6": "DE6",
    "DE7": "DE7",
    "PR0": "PR0",
    "RE0": "RE0",
    "RE1": "RE1",
    "RE2": "RE2",
    "RE3": "RE3",
    "RE4": "RE4",
    "RE5": "RE5",
    "RE6": "RE6",
    "RE7": "RE7",
}


def _extrair_codigo_base_historico(historico: str) -> str:
    """
    Extrai codigo-base (CPV/DEV/DE*/RE*/PR0) do historico.
    """
    if pd.isna(historico) or not str(historico).strip():
        return ""

    texto = str(historico).strip().upper()
    # Aceita variacoes com separadores: "PR 0", "PR-0", "DE 7", "RE/0", "CPV/PD/BO"
    match = re.search(r"(CPV|BON|DEV|DE\D*[0-7]|RE\D*[0-7]|PR\D*0)", texto)
    if match:
        bruto = match.group(1)
        normalizado = re.sub(r"\D", "", bruto)
        if bruto.startswith("DE") and normalizado:
            return f"DE{normalizado[-1]}"
        if bruto.startswith("RE") and normalizado:
            return f"RE{normalizado[-1]}"
        if bruto.startswith("PR") and normalizado:
            return "PR0"
        if bruto.startswith("CPV"):
            return "CPV"
        if bruto.startswith("BON"):
            return "BON"
        if bruto.startswith("DEV"):
            return "DEV"
    return texto[:3].strip()


def extrair_cf_original(historico: str) -> str:
    """
    Extrai o codigo original (primeiros 3 caracteres) do HISTORICO sem mapeamento.

    Exemplos:
    - "DE7 | TRANSFERENCIA DESTINO DATA: 25/11/" -> "DE7"
    - "CPV CFOP: 5101 NF 000034619" -> "CPV"
    - "RE0 | REQUISICAO DATA: 15/11/" -> "RE0"
    """
    return _extrair_codigo_base_historico(historico)


def extrair_codigo_movimento(historico: str) -> str:
    """
    Extrai codigo de movimento dos primeiros 3 caracteres do HISTORICO
    e aplica mapeamento.

    Para CPV: extrai CFOP do historico (ex: "CPV CFOP: 5101 NF..." -> "5101")
    Para DEV: mantem como "DEV"
    Demais: aplica mapeamento DE0-DE7->ENTRADAS, RE0-RE7->SAIDAS

    Exemplos:
    - "DE7 | TRANSFERENCIA DESTINO DATA: 25/11/" -> "ENTRADAS"
    - "CPV CFOP: 5101 NF 000034619" -> "5101"
    - "CPV CFOP: 6102 NF 000054321" -> "6102"
    - "DEV CFOP: 1201 NF 000012345" -> "DEV"
    - "RE0 | REQUISICAO DATA: 15/11/" -> "SAIDAS"
    - "PR0 | PRODUCAO DATA: 20/11/" -> "ENTRADAS"
    """
    codigo = _extrair_codigo_base_historico(historico)

    # Aplicar mapeamento (CPV->CPV, DEV->DEV, DE0->ENTRADAS, etc)
    return MAPEAMENTO_CODIGO_RAZAO.get(codigo, codigo)


def extrair_data_historico(historico: str, ano_base: int = None) -> str:
    """
    Extrai data do texto do HISTORICO.

    Padroes:
    - "... DATA: 25/11/2025" -> "25/11/2025"
    - "... DATA: 25/11/25" -> "25/11/2025"
    - "... DATA: 25/11/" -> "25/11/{ano_base}"
    - "... DATA: 25/11" -> "25/11/{ano_base}"

    Se o ano nao estiver presente, usa ano_base (do parametro data_base).

    Returns:
        Data no formato DD/MM/YYYY ou "" se nao encontrar
    """
    if pd.isna(historico) or not str(historico).strip():
        return ""

    texto = str(historico).strip()

    def _fmt_dmy(d: str, m: str, y: str) -> str:
        return f"{d.zfill(2)}/{m.zfill(2)}/{y}"

    def _resolver_ano(y_extraido: str) -> str:
        # Regra solicitada: usar sempre o ano informado na rotina, quando disponivel.
        if ano_base:
            return str(ano_base)
        return y_extraido

    def _fmt_dmy_ano_base(d: str, m: str) -> str:
        if ano_base:
            return f"{d.zfill(2)}/{m.zfill(2)}/{ano_base}"
        return ""

    # Padrao 1: DATA: DD/MM/YYYY (ano completo)
    match = re.search(r'DATA:\s*(\d{1,2})/(\d{1,2})/(\d{4})', texto)
    if match:
        return _fmt_dmy(match.group(1), match.group(2), _resolver_ano(match.group(3)))

    # Padrao 2: DATA: DD/MM/YY (ano curto)
    match = re.search(r'DATA:\s*(\d{1,2})/(\d{1,2})/(\d{2})\b', texto)
    if match:
        ano_curto = int(match.group(3))
        ano = 2000 + ano_curto if ano_curto < 50 else 1900 + ano_curto
        return _fmt_dmy(match.group(1), match.group(2), _resolver_ano(str(ano)))

    # Padrao 3: DATA: DD/MM/ (sem ano - trailing slash)
    match = re.search(r'DATA:\s*(\d{1,2})/(\d{1,2})/', texto)
    if match:
        return _fmt_dmy_ano_base(match.group(1), match.group(2))

    # Padrao 4: DATA: DD/MM (sem barra final, sem ano)
    match = re.search(r'DATA:\s*(\d{1,2})/(\d{1,2})(?:\s|$|[^/\d])', texto)
    if match:
        return _fmt_dmy_ano_base(match.group(1), match.group(2))

    # Fallback 5: DD/MM/YYYY em qualquer trecho do historico
    match = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)', texto)
    if match:
        return _fmt_dmy(match.group(1), match.group(2), _resolver_ano(match.group(3)))

    # Fallback 6: DD/MM/YY em qualquer trecho do historico
    match = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{2})(?!\d)', texto)
    if match:
        ano_curto = int(match.group(3))
        ano = 2000 + ano_curto if ano_curto < 50 else 1900 + ano_curto
        return _fmt_dmy(match.group(1), match.group(2), _resolver_ano(str(ano)))

    # Fallback 7: DD/MM/ sem ano em qualquer trecho
    match = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})/(?!\d)', texto)
    if match:
        return _fmt_dmy_ano_base(match.group(1), match.group(2))

    # Fallback 8: DD/MM sem ano em qualquer trecho
    match = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})(?!/\d)', texto)
    if match:
        return _fmt_dmy_ano_base(match.group(1), match.group(2))

    return ""


def normalizar_razao_estoque(entrada: Any, ano_base: int = None) -> pd.DataFrame:
    """
    Normaliza relatorio de Razao Contabil de Estoque (CTBR400).

    Mesmo layout do Razao de Banco, mas:
    - Extrai codigo de movimento de HISTORICO[:3] (com mapeamento CPV/DEV)
    - Extrai data de movimentacao do texto HISTORICO (padrao DATA: DD/MM/)
    - NAO usa coluna DATA para agrupamento (usa data extraida do historico)

    Args:
        entrada: DataFrame ou caminho para arquivo Excel
        ano_base: Ano para completar datas sem ano no historico

    Retorna DataFrame com colunas:
    - data_lancamento: Data da coluna DATA (apenas informativa)
    - data_movimento: Data extraida do HISTORICO (para matching com Kardex)
    - historico: Texto completo do historico
    - lote_doc: Lote/Sub/Doc/Linha original
    - codigo_movimento: Codigo mapeado (DE7, RE0, SAIDAS, ENTRADAS, etc)
    - debito: Valor de debito
    - credito: Valor de credito
    - valor: debito - credito
    - tipo: DEBITO ou CREDITO
    - saldo_atual: Saldo apos lancamento
    """
    logger.info("[RAZAO ESTOQUE] Iniciando normalizacao")

    # 1. CARREGAR DATAFRAME
    if isinstance(entrada, pd.DataFrame):
        df = entrada.copy()
    elif isinstance(entrada, str):
        df = pd.read_excel(entrada)
    else:
        raise ValueError("entrada deve ser DataFrame ou caminho de arquivo")

    logger.info(f"[RAZAO ESTOQUE] Registros lidos: {len(df)}")
    logger.info(f"[RAZAO ESTOQUE] Colunas originais: {list(df.columns)}")

    # 2. NORMALIZAR COLUNAS
    df = normalizar_nome_colunas(df)
    logger.info(f"[RAZAO ESTOQUE] Colunas normalizadas: {list(df.columns)}")

    # 3. MAPEAR COLUNAS
    col_data = obter_coluna(df, ["data", "dt", "data_lancamento", "data_lanc"])
    col_historico = obter_coluna(df, ["historico", "hist", "descricao"])
    col_debito = obter_coluna(df, ["debito", "deb", "valor_debito"])
    col_credito = obter_coluna(df, ["credito", "cred", "valor_credito"])
    col_saldo = obter_coluna(df, ["saldo_atual", "saldo", "saldo_final"])
    col_lote_doc = obter_coluna(df, ["lote_sub_doc_linha", "lote", "documento", "doc"])

    logger.info(f"[RAZAO ESTOQUE] Coluna DATA: {col_data}")
    logger.info(f"[RAZAO ESTOQUE] Coluna HISTORICO: {col_historico}")
    logger.info(f"[RAZAO ESTOQUE] Coluna DEBITO: {col_debito}")
    logger.info(f"[RAZAO ESTOQUE] Coluna CREDITO: {col_credito}")

    if not col_historico:
        raise ValueError(f"Coluna de HISTORICO nao encontrada. Colunas: {list(df.columns)}")
    if not col_debito and not col_credito:
        raise ValueError(f"Colunas de DEBITO/CREDITO nao encontradas. Colunas: {list(df.columns)}")

    # 4. PROCESSAR DADOS
    df_norm = pd.DataFrame()

    # Data do lancamento (coluna DATA - apenas informativa)
    if col_data:
        df_norm["data_lancamento"] = df[col_data].apply(formatar_data)
    else:
        df_norm["data_lancamento"] = ""

    # Historico completo
    df_norm["historico"] = df[col_historico].astype(str).str.strip()

    # Lote/Doc (informativo)
    if col_lote_doc:
        df_norm["lote_doc"] = df[col_lote_doc].astype(str).str.strip()
    else:
        df_norm["lote_doc"] = ""

    # Extrair CF original (3 primeiros caracteres do historico, sem mapeamento)
    df_norm["cf_original"] = df_norm["historico"].apply(extrair_cf_original)

    # Extrair codigo de movimento do historico (com mapeamento para ENTRADAS/SAIDAS)
    df_norm["codigo_movimento"] = df_norm["historico"].apply(extrair_codigo_movimento)

    # Regra explicita de segmentacao: PR0 permanece PR0 no Razao
    mask_pr0 = df_norm["cf_original"] == "PR0"
    if mask_pr0.any():
        df_norm.loc[mask_pr0, "codigo_movimento"] = "PR0"

    # Extrair data de movimento do historico (esta e a data usada para matching)
    df_norm["data_movimento"] = df_norm["historico"].apply(
        lambda h: extrair_data_historico(h, ano_base)
    )
    # Fallback: se nao encontrou data no historico, usa data da coluna DATA
    mask_sem_data_mov = df_norm["data_movimento"].astype(str).str.strip() == ""
    if mask_sem_data_mov.any():
        df_norm.loc[mask_sem_data_mov, "data_movimento"] = df_norm.loc[mask_sem_data_mov, "data_lancamento"]
        logger.info(
            "[RAZAO ESTOQUE] Datas de movimento preenchidas por fallback da DATA: %s",
            int(mask_sem_data_mov.sum()),
        )

    # Valores debito/credito
    if col_debito:
        df_norm["debito"] = df[col_debito].apply(parse_numero_brasileiro).abs()
    else:
        df_norm["debito"] = 0.0

    if col_credito:
        df_norm["credito"] = df[col_credito].apply(parse_numero_brasileiro).abs()
    else:
        df_norm["credito"] = 0.0

    # Valor liquido e tipo
    df_norm["valor"] = df_norm["debito"] - df_norm["credito"]
    df_norm["tipo"] = "DEBITO"
    df_norm.loc[df_norm["credito"] > 0, "tipo"] = "CREDITO"

    # Fallback: codigos nao mapeados -> classificar por debito/credito
    mask_nao_mapeado = ~df_norm["codigo_movimento"].isin([
        "ENTRADAS", "SAIDAS", "CPV", "DEV", "PR0",
        "DE0", "DE1", "DE2", "DE3", "DE4", "DE5", "DE6", "DE7",
        "RE0", "RE1", "RE2", "RE3", "RE4", "RE5", "RE6", "RE7",
        ""
    ])
    if mask_nao_mapeado.any():
        codigos_nao_mapeados = df_norm.loc[mask_nao_mapeado, "codigo_movimento"].unique().tolist()
        logger.warning(f"[RAZAO ESTOQUE] Codigos nao mapeados encontrados: {codigos_nao_mapeados}")
        # Debito > 0 -> ENTRADAS, Credito > 0 -> SAIDAS
        mask_debito = mask_nao_mapeado & (df_norm["debito"] > 0)
        mask_credito = mask_nao_mapeado & (df_norm["credito"] > 0)
        df_norm.loc[mask_debito, "codigo_movimento"] = "ENTRADAS"
        df_norm.loc[mask_credito, "codigo_movimento"] = "SAIDAS"

    # Saldo
    if col_saldo:
        df_norm["saldo_atual"] = df[col_saldo].apply(parse_numero_brasileiro)
    else:
        df_norm["saldo_atual"] = 0.0

    # 5. LIMPAR
    df_norm = df_norm[(df_norm["debito"] != 0) | (df_norm["credito"] != 0)].copy()

    logger.info(f"[RAZAO ESTOQUE] Lancamentos normalizados: {len(df_norm)}")
    logger.info(f"[RAZAO ESTOQUE] Total debitos: {df_norm['debito'].sum():,.2f}")
    logger.info(f"[RAZAO ESTOQUE] Total creditos: {df_norm['credito'].sum():,.2f}")
    logger.info(f"[RAZAO ESTOQUE] Codigos de movimento: {df_norm['codigo_movimento'].unique().tolist()}")
    logger.info(f"[RAZAO ESTOQUE] Datas de movimento extraidas: {df_norm['data_movimento'].nunique()} unicas")

    return df_norm
