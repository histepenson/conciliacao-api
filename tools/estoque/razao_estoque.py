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

# LPs (Lancamento Padrao) que tratam devolucao no Razao -- confirmado que sao
# 2 LPs diferentes: um pra devolucao de compra (nos devolvemos mercadoria a
# um fornecedor) e outro pra devolucao de venda (cliente devolve mercadoria
# pra nos). O historico do Razao ("DEV NF. 2/000023750-...") nao traz CFOP,
# entao a segmentacao usa o LP (ct2_lp) do lancamento, nao o texto.
DEV_LP_COMPRA = {"672"}
DEV_LP_VENDA = {"641"}

logger = logging.getLogger(__name__)

# Mapeamento de codigos do Razao para codigos de agrupamento
# Todos os movimentos sao aglutinados em ENTRADAS ou SAIDAS
MAPEAMENTO_CODIGO_RAZAO = {
    "CPV": "CPV",
    "CMV": "CPV",  # mesma coisa que CPV, so' nomenclatura diferente por empresa
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


def _extrair_codigo_base_historico(historico: str, estrito: bool = False) -> str:
    """
    Extrai codigo-base (CPV/DEV/DE*/RE*/PR0) do historico.
    """
    if pd.isna(historico) or not str(historico).strip():
        return ""

    texto = str(historico).strip().upper()
    # Aceita variacoes com separadores: "PR 0", "PR-0", "DE 7", "RE/0", "CPV/PD/BO"
    # CMV e' a mesma coisa que CPV (nomenclatura diferente por empresa -- ver
    # MAPEAMENTO_CODIGO_RAZAO), ja' normalizado aqui pra "CPV".
    if estrito:
        # Modo estrito (so' empresas com a particularidade
        # estoque_razao_ct2razct5): o codigo precisa estar no INICIO do
        # historico e so' admite separador (nao-alfanumerico) entre as letras
        # e o digito. Sem isso o "RE" de "CREDITADO" + o numero da nota virava
        # RE0-RE7 ("COFINS CREDITADO NFE 2414" -> RE2), e o mesmo vale pra
        # DE/PR dentro de qualquer palavra.
        match = re.match(r"\s*(CPV|CMV|BON|DEV|DE[^A-Z0-9]*[0-7]|RE[^A-Z0-9]*[0-7]|PR[^A-Z0-9]*0)", texto)
    else:
        match = re.search(r"(CPV|CMV|BON|DEV|DE\D*[0-7]|RE\D*[0-7]|PR\D*0)", texto)
    if match:
        bruto = match.group(1)
        normalizado = re.sub(r"\D", "", bruto)
        if bruto.startswith("DE") and normalizado:
            return f"DE{normalizado[-1]}"
        if bruto.startswith("RE") and normalizado:
            return f"RE{normalizado[-1]}"
        if bruto.startswith("PR") and normalizado:
            return "PR0"
        if bruto.startswith("CPV") or bruto.startswith("CMV"):
            return "CPV"
        if bruto.startswith("BON"):
            return "BON"
        if bruto.startswith("DEV"):
            return "DEV"
    return texto[:3].strip()


def extrair_cf_original(historico: str, estrito: bool = False) -> str:
    """
    Extrai o codigo original (primeiros 3 caracteres) do HISTORICO sem mapeamento.

    Exemplos:
    - "DE7 | TRANSFERENCIA DESTINO DATA: 25/11/" -> "DE7"
    - "CPV CFOP: 5101 NF 000034619" -> "CPV"
    - "RE0 | REQUISICAO DATA: 15/11/" -> "RE0"
    """
    return _extrair_codigo_base_historico(historico, estrito)


def extrair_codigo_movimento(historico: str, estrito: bool = False) -> str:
    """
    Extrai codigo de movimento dos primeiros 3 caracteres do HISTORICO
    e aplica mapeamento.

    Para DEV: mantem como "DEV" nesta etapa -- o historico real nao traz
    CFOP embutido (ex.: "DEV NF. 2/000023750-KUHN DO BRASIL"), entao a
    segmentacao em "DEV - COMPRA" x "DEV - VENDA" e' feita depois, em
    normalizar_razao_estoque(), usando o LP (ct2_lp) do lancamento -- ver
    DEV_LP_COMPRA / DEV_LP_VENDA.
    Demais: aplica mapeamento DE0-DE7->ENTRADAS, RE0-RE7->SAIDAS

    Exemplos:
    - "DE7 | TRANSFERENCIA DESTINO DATA: 25/11/" -> "ENTRADAS"
    - "DEV NF. 2/000023750-KUHN DO BRASIL" -> "DEV"
    - "RE0 | REQUISICAO DATA: 15/11/" -> "SAIDAS"
    - "PR0 | PRODUCAO DATA: 20/11/" -> "ENTRADAS"
    """
    codigo = _extrair_codigo_base_historico(historico, estrito)

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

    def _dia_mes_validos(d: str, m: str) -> bool:
        try:
            return 1 <= int(d) <= 31 and 1 <= int(m) <= 12
        except ValueError:
            return False

    def _fmt_dmy(d: str, m: str, y: str) -> str:
        if not _dia_mes_validos(d, m):
            return ""
        return f"{d.zfill(2)}/{m.zfill(2)}/{y}"

    def _resolver_ano(y_extraido: str) -> str:
        # Regra solicitada: usar sempre o ano informado na rotina, quando disponivel.
        if ano_base:
            return str(ano_base)
        return y_extraido

    def _fmt_dmy_ano_base(d: str, m: str) -> str:
        if not ano_base or not _dia_mes_validos(d, m):
            return ""
        return f"{d.zfill(2)}/{m.zfill(2)}/{ano_base}"

    # Os fallbacks soltos (5-8) procuram DD/MM em qualquer trecho do texto
    # -- em historicos sem "DATA:" (ex.: "NFE. 1/000000360-FORNECEDOR"), a
    # serie/numero da NF ("1/000000360") pode casar por acidente, gerando
    # dia/mes invalidos tipo "01/00". Cada padrao abaixo so' retorna se o
    # dia/mes extraido for uma data valida (_dia_mes_validos); senao,
    # continua tentando os proximos padroes -- se nenhum bater, cai no
    # fallback de normalizar_razao_estoque que usa a coluna DATA real.

    # Padrao 1: DATA: DD/MM/YYYY (ano completo)
    match = re.search(r'DATA:\s*(\d{1,2})/(\d{1,2})/(\d{4})', texto)
    if match:
        resultado = _fmt_dmy(match.group(1), match.group(2), _resolver_ano(match.group(3)))
        if resultado:
            return resultado

    # Padrao 2: DATA: DD/MM/YY (ano curto)
    match = re.search(r'DATA:\s*(\d{1,2})/(\d{1,2})/(\d{2})\b', texto)
    if match:
        ano_curto = int(match.group(3))
        ano = 2000 + ano_curto if ano_curto < 50 else 1900 + ano_curto
        resultado = _fmt_dmy(match.group(1), match.group(2), _resolver_ano(str(ano)))
        if resultado:
            return resultado

    # Padrao 3: DATA: DD/MM/ (sem ano - trailing slash)
    match = re.search(r'DATA:\s*(\d{1,2})/(\d{1,2})/', texto)
    if match:
        resultado = _fmt_dmy_ano_base(match.group(1), match.group(2))
        if resultado:
            return resultado

    # Padrao 4: DATA: DD/MM (sem barra final, sem ano)
    match = re.search(r'DATA:\s*(\d{1,2})/(\d{1,2})(?:\s|$|[^/\d])', texto)
    if match:
        resultado = _fmt_dmy_ano_base(match.group(1), match.group(2))
        if resultado:
            return resultado

    # Fallback 5: DD/MM/YYYY em qualquer trecho do historico
    match = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)', texto)
    if match:
        resultado = _fmt_dmy(match.group(1), match.group(2), _resolver_ano(match.group(3)))
        if resultado:
            return resultado

    # Fallback 6: DD/MM/YY em qualquer trecho do historico
    match = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})/(\d{2})(?!\d)', texto)
    if match:
        ano_curto = int(match.group(3))
        ano = 2000 + ano_curto if ano_curto < 50 else 1900 + ano_curto
        resultado = _fmt_dmy(match.group(1), match.group(2), _resolver_ano(str(ano)))
        if resultado:
            return resultado

    # Fallback 7: DD/MM/ sem ano em qualquer trecho
    match = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})/(?!\d)', texto)
    if match:
        resultado = _fmt_dmy_ano_base(match.group(1), match.group(2))
        if resultado:
            return resultado

    # Fallback 8: DD/MM sem ano em qualquer trecho
    match = re.search(r'(?<!\d)(\d{1,2})/(\d{1,2})(?!/\d)', texto)
    if match:
        resultado = _fmt_dmy_ano_base(match.group(1), match.group(2))
        if resultado:
            return resultado

    return ""


def _sequencia_do_origem(origem: Any) -> str:
    """Extrai a sequencia do LP do prefixo "LP-SEQ" de ct2_origem (ex.:
    "650-002 - usuario" -> "002")."""
    partes = str(origem or "").strip()[:7].split("-")
    return partes[1].strip() if len(partes) == 2 else ""


def _chave_nota(row: Any) -> str:
    """Chave que liga os lancamentos de uma mesma nota: o CT2_KEY quando
    veio preenchido; senao data + LP + numero da nota (ultimo token do
    historico, ex.: "ICMS CREDITADO NFE 2414" -> "2414")."""
    key = str(row["ct2_key"] or "").strip()
    if key:
        return f"K|{key}"
    tokens = str(row["historico"] or "").split()
    nota = tokens[-1] if tokens else ""
    return f"H|{row['data_lancamento']}|{row['ct2_lp']}|{nota}"


def abater_creditos_imposto(df_norm: pd.DataFrame, mapa_lp_sequencias_credito: Optional[dict]) -> pd.DataFrame:
    """
    Remove do razao os lancamentos de CREDITO DE IMPOSTO recuperavel (ICMS/
    PIS/COFINS) dos LPs de estoque configurados e abate o valor do
    lancamento de compra (debito) da mesma nota.

    O Kardex ja' entra liquido desses impostos (custo = NF - ICMS - PIS -
    COFINS), entao o razao da nota so' fecha com o Kardex depois do abatimento.
    Ex.: NF 2414 = 52.189,72 (debito) - 13.259,40 - 642,35 - 2.958,70 =
    35.329,27 (= Kardex).

    Isolado por configuracao: so' mexe em linhas cujo (ct2_lp, ct2_sequen)
    esta em mapa_lp_sequencias_credito ({lp_codigo: {sequencias}}, ver
    services/lancamento_padrao_ct2_service.py::obter_mapa_sequencias_credito_imposto).
    Sem mapa (LP/empresa nao configurado) devolve o DataFrame intacto.
    Credito que nao achar o debito da mesma nota fica no razao, pra nao
    perder valor em silencio.
    """
    if not mapa_lp_sequencias_credito or df_norm.empty:
        return df_norm

    df = df_norm.copy()
    lp = df["ct2_lp"].astype(str).str.strip()
    seq = df["ct2_sequen"].astype(str).str.strip()
    eh_credito_imposto = pd.Series(
        [s in mapa_lp_sequencias_credito.get(l, ()) for l, s in zip(lp, seq)], index=df.index
    ) & (df["credito"] > 0) & (df["debito"] == 0)
    if not eh_credito_imposto.any():
        return df_norm

    df["_chave_nota"] = df.apply(_chave_nota, axis=1)
    creditos_por_nota = df.loc[eh_credito_imposto].groupby("_chave_nota")["credito"].sum()

    remover = []
    for chave, total in creditos_por_nota.items():
        candidatos = df[(df["_chave_nota"] == chave) & ~eh_credito_imposto & (df["debito"] > 0)]
        if candidatos.empty:
            continue
        idx_debito = candidatos["debito"].idxmax()
        if df.at[idx_debito, "debito"] < total:
            continue
        df.at[idx_debito, "debito"] = round(float(df.at[idx_debito, "debito"]) - float(total), 2)
        remover.extend(df.index[eh_credito_imposto & (df["_chave_nota"] == chave)].tolist())

    if remover:
        logger.info(
            "[RAZAO ESTOQUE] Creditos de imposto abatidos da nota: %s lancamentos | total=%.2f",
            len(remover), float(df.loc[remover, "credito"].sum()),
        )
    return df.drop(index=remover).drop(columns=["_chave_nota"])


def normalizar_razao_estoque(
    entrada: Any,
    ano_base: int = None,
    mapa_lp_sequencias_credito: Optional[dict] = None,
    historico_estrito: bool = False,
    regras_historico_movimento: Optional[list] = None,
) -> pd.DataFrame:
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
    - ct2_key: CT2_KEY de origem, quando disponivel no CTBR400 (vazio em
      cargas antigas sem esse campo)
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
    col_ct2_key = obter_coluna(df, ["ct2_key"])
    col_ct2_lp = obter_coluna(df, ["ct2_lp"])
    col_ct2_sequen = obter_coluna(df, ["ct2_sequen"])
    col_ct2_origem = obter_coluna(df, ["ct2_origem"])
    col_conta = obter_coluna(df, ["conta", "conta_contabil"])

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

    # ct2_key: presente quando o CTBR400 (real ou importado manualmente) traz
    # o CT2_KEY de origem -- permite matching exato contra o ct2_key montado
    # no Kardex, em vez de so' (data, cf) agregado. Ausente em cargas antigas.
    if col_ct2_key:
        df_norm["ct2_key"] = df[col_ct2_key].astype(str).str.strip()
    else:
        df_norm["ct2_key"] = ""

    # ct2_lp: LP (lancamento padrao) que gerou o lancamento na CT2 -- usado
    # pra escolher qual formula de ct2_key aplicar do lado do Kardex (a
    # formula varia por LP). Ausente em cargas antigas.
    if col_ct2_lp:
        df_norm["ct2_lp"] = df[col_ct2_lp].astype(str).str.strip()
    else:
        df_norm["ct2_lp"] = ""

    # ct2_sequen: sequencia do LP (CT5_SEQUEN) -- so' vem no CT2RAZCT5. Cargas
    # antigas sem o campo caem no prefixo "LP-SEQ" de ct2_origem.
    if mapa_lp_sequencias_credito:
        df_norm["ct2_sequen"] = ""
        if col_ct2_sequen:
            df_norm["ct2_sequen"] = df[col_ct2_sequen].astype(str).str.strip()
        if col_ct2_origem:
            sem_seq = df_norm["ct2_sequen"].isin(["", "nan", "None"])
            if sem_seq.any():
                df_norm.loc[sem_seq, "ct2_sequen"] = df.loc[sem_seq, col_ct2_origem].apply(_sequencia_do_origem)

    # conta_contabil: conta do lancamento (campo "conta" do CTBR400) -- usada
    # pela consulta de divergencia Kardex->Razao pra informar em qual conta
    # um movimento so' kardex foi encontrado. Ausente em cargas antigas.
    if col_conta:
        df_norm["conta_contabil"] = df[col_conta].astype(str).str.strip()
    else:
        df_norm["conta_contabil"] = ""

    # Extrair CF original (3 primeiros caracteres do historico, sem mapeamento)
    df_norm["cf_original"] = df_norm["historico"].apply(lambda h: extrair_cf_original(h, historico_estrito))

    # Extrair codigo de movimento do historico (com mapeamento para ENTRADAS/SAIDAS)
    df_norm["codigo_movimento"] = df_norm["historico"].apply(lambda h: extrair_codigo_movimento(h, historico_estrito))

    # Regra explicita de segmentacao: PR0 permanece PR0 no Razao
    mask_pr0 = df_norm["cf_original"] == "PR0"
    if mask_pr0.any():
        df_norm.loc[mask_pr0, "codigo_movimento"] = "PR0"

    # Regras de historico por empresa (particularidade): historico que COMECA com
    # um prefixo conhecido vira um codigo de movimento fixo, mas so' nos
    # lancamentos SEM CT2_KEY -- com a chave preenchida quem classifica e' o
    # casamento pelo layout do LP contra o Kardex. Ex.: Rancheiro, "BX INSUMOS
    # OP ..." -> RE1 (baixa de insumo por ordem de producao).
    if regras_historico_movimento:
        hist_norm = df_norm["historico"].astype(str).str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
        sem_key = df_norm["ct2_key"].astype(str).str.strip().isin(["", "nan", "None"])
        for prefixo, codigo in regras_historico_movimento:
            mask_regra = sem_key & hist_norm.str.startswith(str(prefixo).upper())
            if mask_regra.any():
                df_norm.loc[mask_regra, "codigo_movimento"] = codigo
                df_norm.loc[mask_regra, "cf_original"] = codigo
                logger.info(
                    "[RAZAO ESTOQUE] Regra de historico %r -> %s (sem CT2_KEY): %s lancamentos",
                    prefixo, codigo, int(mask_regra.sum()),
                )

    # DEV segmentado por LP: sao 2 lancamentos padrao diferentes (devolucao
    # de compra x devolucao de venda), cruzam com CFOPs diferentes no
    # Kardex e nao podem ficar agrupados juntos na grid.
    mask_dev = df_norm["codigo_movimento"] == "DEV"
    if mask_dev.any() and "ct2_lp" in df_norm.columns:
        df_norm.loc[mask_dev & df_norm["ct2_lp"].isin(DEV_LP_COMPRA), "codigo_movimento"] = "DEV - COMPRA"
        df_norm.loc[mask_dev & df_norm["ct2_lp"].isin(DEV_LP_VENDA), "codigo_movimento"] = "DEV - VENDA"

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

    # Creditos de imposto (ICMS/PIS/COFINS) dos LPs de estoque configurados:
    # abatidos da propria nota, ja' que o Kardex entra liquido de imposto.
    df_norm = abater_creditos_imposto(df_norm, mapa_lp_sequencias_credito)

    # Valor liquido e tipo
    df_norm["valor"] = df_norm["debito"] - df_norm["credito"]
    df_norm["tipo"] = "DEBITO"
    df_norm.loc[df_norm["credito"] > 0, "tipo"] = "CREDITO"

    # Fallback: codigos nao mapeados -> classificar por debito/credito
    mask_nao_mapeado = ~df_norm["codigo_movimento"].isin([
        "ENTRADAS", "SAIDAS", "CPV", "DEV", "DEV - COMPRA", "DEV - VENDA", "PR0",
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
