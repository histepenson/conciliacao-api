"""
Modulo de calculo de diferencas para Conciliacao Bancaria.

Realiza o matching entre extrato bancario (FINR470) e razao contabil (CTBR400):
- Agrupa movimentos por dia
- Compara totais de entradas/saidas por dia
- Classifica divergencias
- Identifica registros sem correspondencia

Regras contabeis (conta bancaria = ATIVO):
- Entrada no extrato (FIN) = Debito no razao (CTBR400)
- Saida no extrato (FIN) = Credito no razao (CTBR400)
"""

import pandas as pd
import logging
import re
from typing import Dict, List, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Threshold para considerar valores iguais (R$ 0,01)
THRESHOLD_CONCILIACAO = 0.01


def _normalizar_numero_documento(valor: Any) -> str:
    """Extrai e concatena todos os digitos do documento, removendo zeros a esquerda."""
    if pd.isna(valor):
        return ""
    s = str(valor)
    # Concatenar TODOS os grupos de digitos (ex: "63616-055" -> "63616055")
    numeros = re.findall(r"\d+", s)
    if not numeros:
        return ""
    concatenado = "".join(numeros)
    # Remover zeros a esquerda para normalizar
    return concatenado.lstrip("0") or "0"


def _key_documento(df: pd.DataFrame) -> pd.Series:
    if "numero" in df.columns:
        return df["numero"].fillna("").astype(str).apply(_normalizar_numero_documento)
    if "documento_extraido" in df.columns:
        return df["documento_extraido"].fillna("").astype(str).apply(_normalizar_numero_documento)
    if "chave_documento" in df.columns:
        return df["chave_documento"].fillna("").astype(str).apply(_normalizar_numero_documento)
    return pd.Series([""] * len(df), index=df.index)


def _match_exato_doc_valor(df_ext: pd.DataFrame, df_raz: pd.DataFrame, col_ext: str, col_raz: str) -> None:
    """
    FASE 1: documento + valor exatos.
    Indexa o razao por _doc_key uma unica vez em vez de filtrar o DataFrame
    inteiro (`df_raz[... & (df_raz["_doc_key"] == chave)]`) para cada linha
    do extrato -- isso era O(N*M) e era o maior gargalo com milhares de
    registros (roda antes de qualquer outra fase).
    """
    raz_por_chave: dict[str, list] = {}
    for idx_raz, chave_raz in df_raz["_doc_key"].items():
        if chave_raz:
            raz_por_chave.setdefault(chave_raz, []).append(idx_raz)

    for idx_ext in df_ext.index:
        if df_ext.loc[idx_ext, "matched"]:
            continue
        chave = df_ext.loc[idx_ext, "_doc_key"]
        if not chave:
            continue
        valor_ext = df_ext.loc[idx_ext, col_ext]
        for idx_raz in raz_por_chave.get(chave, []):
            if df_raz.loc[idx_raz, "matched"]:
                continue
            valor_raz = df_raz.loc[idx_raz, col_raz]
            if abs(valor_ext - valor_raz) <= THRESHOLD_CONCILIACAO:
                df_ext.loc[idx_ext, "matched"] = True
                df_raz.loc[idx_raz, "matched"] = True
                df_ext.loc[idx_ext, "data_correspondencia"] = df_raz.loc[idx_raz, "data"]
                df_raz.loc[idx_raz, "data_correspondencia"] = df_ext.loc[idx_ext, "data"]
                break


def _match_soma_por_documento(df_ext: pd.DataFrame, df_raz: pd.DataFrame, col_ext: str, col_raz: str) -> None:
    pend_ext = df_ext[~df_ext["matched"] & (df_ext["_doc_key"].str.len() > 0)]
    pend_raz = df_raz[~df_raz["matched"] & (df_raz["_doc_key"].str.len() > 0)]
    if pend_ext.empty or pend_raz.empty:
        return
    soma_ext = pend_ext.groupby("_doc_key")[col_ext].sum()
    soma_raz = pend_raz.groupby("_doc_key")[col_raz].sum()
    for chave in set(soma_ext.index).intersection(set(soma_raz.index)):
        if abs(soma_ext[chave] - soma_raz[chave]) <= THRESHOLD_CONCILIACAO:
            idx_ext_grupo = pend_ext[pend_ext["_doc_key"] == chave].index
            idx_raz_grupo = pend_raz[pend_raz["_doc_key"] == chave].index
            datas_raz = ", ".join(sorted(set(df_raz.loc[idx_raz_grupo, "data"])))
            datas_ext = ", ".join(sorted(set(df_ext.loc[idx_ext_grupo, "data"])))
            df_ext.loc[idx_ext_grupo, "matched"] = True
            df_ext.loc[idx_ext_grupo, "data_correspondencia"] = datas_raz
            df_raz.loc[idx_raz_grupo, "matched"] = True
            df_raz.loc[idx_raz_grupo, "data_correspondencia"] = datas_ext


def _match_soma_documentos_relacionados(df_ext: pd.DataFrame, df_raz: pd.DataFrame, col_ext: str, col_raz: str) -> None:
    """
    FASE 2.5: Match por soma de documentos relacionados.
    Ex: Extrato 63616055 (10931.97) vs Razao 63616055 (10665.89) + 63616 (266.08)
    Busca no razao documentos cujo numero base esta contido no numero do extrato.

    Indexa o razao por _doc_key (prefixo -> indices) em vez de comparar cada
    linha do extrato contra TODAS as linhas pendentes do razao via .apply()
    -- isso era O(N*M) e virava o gargalo com milhares de registros. Como so'
    interessam prefixos de 3+ caracteres da chave do extrato, o lookup por
    linha fica O(len(chave)) em vez de O(M).
    """
    pend_ext = df_ext[~df_ext["matched"] & (df_ext["_doc_key"].str.len() > 0)]
    pend_raz = df_raz[~df_raz["matched"] & (df_raz["_doc_key"].str.len() > 0)]
    if pend_ext.empty or pend_raz.empty:
        return

    raz_por_chave: dict[str, list] = {}
    for idx_raz, chave_raz in pend_raz["_doc_key"].items():
        raz_por_chave.setdefault(chave_raz, []).append(idx_raz)

    for idx_ext in pend_ext.index:
        if df_ext.loc[idx_ext, "matched"]:
            continue
        chave_ext = df_ext.loc[idx_ext, "_doc_key"]
        valor_ext = df_ext.loc[idx_ext, col_ext]
        if not chave_ext or len(chave_ext) < 4:
            continue

        # Buscar documentos relacionados no razao:
        # 1. Chave exata (63616055)
        # 2. Chave base contida na chave do extrato (63616 em 63616055, 555 em 555032)
        # Ambos os casos sao prefixos de chave_ext de tamanho >= 3.
        candidatos_idx = []
        for tam in range(3, len(chave_ext) + 1):
            candidatos_idx.extend(raz_por_chave.get(chave_ext[:tam], []))
        if not candidatos_idx:
            continue

        relacionados = df_raz.loc[candidatos_idx]
        relacionados = relacionados[~relacionados["matched"]]

        if relacionados.empty:
            continue

        soma_raz = relacionados[col_raz].sum()
        if abs(valor_ext - soma_raz) <= THRESHOLD_CONCILIACAO:
            datas_raz = ", ".join(sorted(set(relacionados["data"])))
            df_ext.loc[idx_ext, "matched"] = True
            df_ext.loc[idx_ext, "data_correspondencia"] = datas_raz
            df_raz.loc[relacionados.index, "matched"] = True
            df_raz.loc[relacionados.index, "data_correspondencia"] = df_ext.loc[idx_ext, "data"]
            logger.debug(f"[FASE 2.5] Match doc relacionados: {chave_ext} = {valor_ext} vs soma({list(relacionados['_doc_key'].values)}) = {soma_raz}")


def _match_fallback_valor(df_ext: pd.DataFrame, df_raz: pd.DataFrame, col_ext: str, col_raz: str) -> None:
    """
    FASE 3: fallback por valor, sem exigir documento nem mesma data.
    Usado como ultimo recurso quando nao ha chave de documento que permita
    casar com seguranca - busca em todo o periodo (nao so no mesmo dia).

    Indexa o razao por centavos do valor (dict) em vez de escanear TODAS as
    linhas nao casadas do razao para cada linha do extrato -- O(N*M) e' o
    pior gargalo desta fase justamente por nao ter chave de documento pra
    restringir os candidatos. A tolerancia (THRESHOLD_CONCILIACAO=0.01, ou
    seja 1 centavo) e' coberta olhando o centavo do valor do extrato e os
    dois vizinhos (-1/+1).
    """
    raz_por_centavo: dict[int, list] = {}
    for idx_raz, valor_raz in df_raz.loc[~df_raz["matched"], col_raz].items():
        centavos = round(valor_raz * 100)
        raz_por_centavo.setdefault(centavos, []).append(idx_raz)

    for idx_ext in df_ext.index:
        if df_ext.loc[idx_ext, "matched"]:
            continue
        valor_ext = df_ext.loc[idx_ext, col_ext]
        centavos_ext = round(valor_ext * 100)

        candidatos_idx = []
        for delta in (0, -1, 1):
            candidatos_idx.extend(raz_por_centavo.get(centavos_ext + delta, []))

        for idx_raz in candidatos_idx:
            if df_raz.loc[idx_raz, "matched"]:
                continue
            valor_raz = df_raz.loc[idx_raz, col_raz]
            if abs(valor_ext - valor_raz) <= THRESHOLD_CONCILIACAO:
                df_ext.loc[idx_ext, "matched"] = True
                df_raz.loc[idx_raz, "matched"] = True
                df_ext.loc[idx_ext, "data_correspondencia"] = df_raz.loc[idx_raz, "data"]
                df_raz.loc[idx_raz, "data_correspondencia"] = df_ext.loc[idx_ext, "data"]
                break


def _sf(v, default=0.0) -> float:
    """Converte para float, retornando default se NaN."""
    return float(v) if pd.notna(v) else default


def _ss(v, default="") -> str:
    """Converte para str, retornando default se NaN."""
    return str(v) if pd.notna(v) else default


def _formatar_extrato(row, tipo: str) -> Dict:
    valor = row.get("entrada", 0) if tipo == "entrada" else row.get("saida", 0)
    return {
        "data": _ss(row.get("data")),
        "documento": _ss(row.get("documento")),
        "prefixo": _ss(row.get("prefixo")),
        "numero": _ss(row.get("numero")),
        "descricao": _ss(row.get("descricao")),
        "valor": round(_sf(valor), 2),
        "tipo": tipo.upper(),
        "data_correspondencia": _ss(row.get("data_correspondencia")),
        "conta_origem": _ss(row.get("conta_origem")),
    }


def _formatar_razao(row, tipo: str) -> Dict:
    valor = row.get("debito", 0) if tipo == "debito" else row.get("credito", 0)
    return {
        "data": _ss(row.get("data")),
        "lote_doc": _ss(row.get("lote_doc")),
        "historico": _ss(row.get("historico")),
        "documento_extraido": _ss(row.get("documento_extraido")),
        "prefixo": _ss(row.get("prefixo")),
        "numero": _ss(row.get("numero")),
        "valor": round(_sf(valor), 2),
        "tipo": tipo.upper(),
        "data_correspondencia": _ss(row.get("data_correspondencia")),
    }


def _fazer_matching_global(
    df_extrato: pd.DataFrame,
    df_razao: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Faz o matching de TODOS os registros do periodo de uma vez, sem restringir
    por dia. Quando a correspondencia e encontrada em uma data diferente da
    data do proprio registro, isso fica registrado em "data_correspondencia"
    para ser exibido ao usuario (o registro continua aparecendo no seu dia
    real, mas marcado como conciliado e com a referencia da data do "par").

    Retorna os 4 DataFrames (entradas_ext, saidas_ext, debitos_raz, creditos_raz)
    com as colunas "matched" e "data_correspondencia" preenchidas.
    """
    entradas_ext = df_extrato[df_extrato["entrada"] > 0].copy()
    saidas_ext = df_extrato[df_extrato["saida"] > 0].copy()
    debitos_raz = df_razao[df_razao["debito"] > 0].copy()
    creditos_raz = df_razao[df_razao["credito"] > 0].copy()

    for df in (entradas_ext, saidas_ext, debitos_raz, creditos_raz):
        df["matched"] = False
        df["data_correspondencia"] = ""

    # Preencher chaves de documento (apenas numeros)
    entradas_ext["_doc_key"] = _key_documento(entradas_ext)
    saidas_ext["_doc_key"] = _key_documento(saidas_ext)
    debitos_raz["_doc_key"] = _key_documento(debitos_raz)
    creditos_raz["_doc_key"] = _key_documento(creditos_raz)

    # FASE 1: DOCUMENTO + VALOR (qualquer data do periodo)
    _match_exato_doc_valor(entradas_ext, debitos_raz, "entrada", "debito")
    _match_exato_doc_valor(saidas_ext, creditos_raz, "saida", "credito")

    # FASE 2: DOCUMENTO (soma)
    _match_soma_por_documento(entradas_ext, debitos_raz, "entrada", "debito")
    _match_soma_por_documento(saidas_ext, creditos_raz, "saida", "credito")

    # FASE 2.5: DOCUMENTOS RELACIONADOS (soma de docs com numero base comum)
    _match_soma_documentos_relacionados(saidas_ext, creditos_raz, "saida", "credito")
    _match_soma_documentos_relacionados(entradas_ext, debitos_raz, "entrada", "debito")

    # FASE 3: VALOR (fallback, busca em todo o periodo - nao so no mesmo dia)
    _match_fallback_valor(entradas_ext, debitos_raz, "entrada", "debito")
    _match_fallback_valor(saidas_ext, creditos_raz, "saida", "credito")

    return entradas_ext, saidas_ext, debitos_raz, creditos_raz


def _filtrar_formatar_dia(
    df: pd.DataFrame, data: str, matched: bool, tipo: str, formatador
) -> List[Dict]:
    """Filtra os registros (ja com matching global feito) que pertencem a um dia especifico."""
    subset = df[(df["data"] == data) & (df["matched"] == matched)]
    return [formatador(row, tipo) for _, row in subset.iterrows()]


def calcular_diferencas_bancarias(
    df_extrato: pd.DataFrame,
    df_razao: pd.DataFrame,
    saldo_final_extrato: float | None = None
) -> Dict[str, Any]:
    """
    Calcula diferencas entre Extrato Bancario e Razao Contabil AGRUPADO POR DIA.

    Parametros:
    -----------
    df_extrato : pd.DataFrame
        DataFrame normalizado do extrato bancario (FINR470). Pode ser a
        combinacao de mais de uma conta bancaria (ver coluna "conta_origem").

    df_razao : pd.DataFrame
        DataFrame normalizado do razao contabil (CTBR400)

    saldo_final_extrato : float | None
        Saldo final ja calculado pelo chamador (soma do saldo final de cada
        conta bancaria antes de combinar os extratos). Quando informado,
        substitui o calculo padrao (ultima linha de df_extrato), que so faz
        sentido quando ha uma unica conta bancaria no dataframe.

    Retorna:
    --------
    dict contendo:
        - 'resumo': Estatisticas da conciliacao
        - 'movimentos_por_dia': Lista de movimentos agrupados por dia
        - 'dias_divergentes': Lista de dias com divergencia
        - 'dias_conciliados': Lista de dias conciliados
    """
    logger.info("[CALC DIFERENCAS BANCO] Iniciando calculo por dia")

    # ==========================
    # DEBUG: MOSTRAR DADOS RECEBIDOS
    # ==========================
    logger.info(f"[CALC DIFERENCAS BANCO] === EXTRATO RECEBIDO ===")
    logger.info(f"[CALC DIFERENCAS BANCO] Colunas: {list(df_extrato.columns)}")
    logger.info(f"[CALC DIFERENCAS BANCO] Registros: {len(df_extrato)}")
    if len(df_extrato) > 0:
        logger.info(f"[CALC DIFERENCAS BANCO] Amostra extrato (5 primeiros):\n{df_extrato.head().to_string()}")

    logger.info(f"[CALC DIFERENCAS BANCO] === RAZAO RECEBIDO ===")
    logger.info(f"[CALC DIFERENCAS BANCO] Colunas: {list(df_razao.columns)}")
    logger.info(f"[CALC DIFERENCAS BANCO] Registros: {len(df_razao)}")
    if len(df_razao) > 0:
        logger.info(f"[CALC DIFERENCAS BANCO] Amostra razao (5 primeiros):\n{df_razao.head().to_string()}")
        if 'debito' in df_razao.columns:
            logger.info(f"[CALC DIFERENCAS BANCO] Total debito no razao: {df_razao['debito'].sum()}")
        if 'credito' in df_razao.columns:
            logger.info(f"[CALC DIFERENCAS BANCO] Total credito no razao: {df_razao['credito'].sum()}")
        if 'data' in df_razao.columns:
            logger.info(f"[CALC DIFERENCAS BANCO] Datas unicas no razao: {df_razao['data'].unique().tolist()[:10]}")

    # ==========================
    # 1. PREPARAR DATAFRAMES
    # ==========================
    df_ext = df_extrato.copy()
    df_raz = df_razao.copy()

    # Garantir data normalizada (DD/MM/YYYY) para aglutinar corretamente por dia
    def _normalizar_data_coluna(df: pd.DataFrame) -> pd.DataFrame:
        if "data" not in df.columns:
            return df
        df = df.copy()
        dt = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
        df["data"] = dt.dt.strftime("%d/%m/%Y")
        df["data"] = df["data"].fillna("").astype(str).str.strip()
        return df

    df_ext = _normalizar_data_coluna(df_ext)
    df_raz = _normalizar_data_coluna(df_raz)

    # Garantir colunas necessarias
    if "entrada" not in df_ext.columns:
        df_ext["entrada"] = 0.0
    if "saida" not in df_ext.columns:
        df_ext["saida"] = 0.0
    if "debito" not in df_raz.columns:
        df_raz["debito"] = 0.0
    if "credito" not in df_raz.columns:
        df_raz["credito"] = 0.0

    # ==========================
    # 2. AGRUPAR EXTRATO POR DIA
    # ==========================
    df_ext_dia = df_ext.groupby("data", as_index=False).agg({
        "entrada": "sum",
        "saida": "sum",
    })
    df_ext_dia.columns = ["data", "entradas_extrato", "saidas_extrato"]

    logger.info(f"[CALC DIFERENCAS BANCO] Dias no extrato: {len(df_ext_dia)}")

    # ==========================
    # 3. AGRUPAR RAZAO POR DIA
    # ==========================
    df_raz_dia = df_raz.groupby("data", as_index=False).agg({
        "debito": "sum",
        "credito": "sum",
    })
    df_raz_dia.columns = ["data", "debitos_razao", "creditos_razao"]

    logger.info(f"[CALC DIFERENCAS BANCO] Dias no razao: {len(df_raz_dia)}")
    logger.info(f"[CALC DIFERENCAS BANCO] Razao agrupado por dia:\n{df_raz_dia.to_string()}")

    # ==========================
    # 4. FAZER MERGE POR DIA
    # ==========================
    df_merge = pd.merge(
        df_ext_dia,
        df_raz_dia,
        on="data",
        how="outer"
    )

    # Preencher NaN com 0
    df_merge = df_merge.fillna(0)

    logger.info(f"[CALC DIFERENCAS BANCO] Total de dias: {len(df_merge)}")
    logger.info(f"[CALC DIFERENCAS BANCO] Merge resultado:\n{df_merge.to_string()}")

    # ==========================
    # 5. CALCULAR DIFERENCAS POR DIA
    # ==========================
    # Regra: Entrada extrato = Debito razao | Saida extrato = Credito razao
    df_merge["dif_entradas"] = df_merge["debitos_razao"] - df_merge["entradas_extrato"]
    df_merge["dif_saidas"] = df_merge["creditos_razao"] - df_merge["saidas_extrato"]
    df_merge["dif_entradas_abs"] = df_merge["dif_entradas"].abs()
    df_merge["dif_saidas_abs"] = df_merge["dif_saidas"].abs()

    # Status do dia
    def classificar_dia(row):
        dif_ent = abs(row["dif_entradas"])
        dif_sai = abs(row["dif_saidas"])

        if dif_ent <= THRESHOLD_CONCILIACAO and dif_sai <= THRESHOLD_CONCILIACAO:
            return "CONCILIADO"

        # Diferenca de entradas igual (em modulo) a diferenca de saidas: indica
        # lancamento classificado como entrada/saida trocado entre extrato e
        # razao (o valor "sobra" de um lado e "falta" do outro na mesma
        # proporcao), o que se anula no total do dia. Nao considerar divergente.
        if dif_ent > THRESHOLD_CONCILIACAO and abs(dif_ent - dif_sai) <= THRESHOLD_CONCILIACAO:
            return "CONCILIADO"

        return "DIVERGENTE"

    def _conciliado_por_compensacao(row):
        dif_ent = abs(row["dif_entradas"])
        dif_sai = abs(row["dif_saidas"])
        ja_conciliado = dif_ent <= THRESHOLD_CONCILIACAO and dif_sai <= THRESHOLD_CONCILIACAO
        return (not ja_conciliado) and dif_ent > THRESHOLD_CONCILIACAO and abs(dif_ent - dif_sai) <= THRESHOLD_CONCILIACAO

    df_merge["status"] = df_merge.apply(classificar_dia, axis=1)
    df_merge["conciliado_por_compensacao"] = df_merge.apply(_conciliado_por_compensacao, axis=1)

    # Ordenar por data
    df_merge = df_merge.sort_values("data")

    # ==========================
    # 6. PREPARAR RESULTADO COM ANALISE DETALHADA
    # ==========================
    movimentos_por_dia = []
    dias_divergentes = []
    dias_conciliados = []

    # Listas globais de registros sem correspondencia
    registros_so_extrato = []
    registros_so_razao = []

    # Matching GLOBAL: roda uma unica vez para todo o periodo (nao mais por dia).
    # Quando o documento/valor casa em uma data diferente, o registro continua
    # aparecendo no seu dia real, marcado como conciliado, com "data_correspondencia"
    # indicando em qual data esta o lancamento que fechou com ele.
    entradas_ext, saidas_ext, debitos_raz, creditos_raz = _fazer_matching_global(df_ext, df_raz)

    for _, row in df_merge.iterrows():
        data_dia = row["data"]
        dif_entradas = row["dif_entradas"]
        dif_saidas = row["dif_saidas"]
        status_dia = row["status"]
        conciliado_por_compensacao = bool(row["conciliado_por_compensacao"])

        so_ext_ent = _filtrar_formatar_dia(entradas_ext, data_dia, False, "entrada", _formatar_extrato)
        conc_ext_ent = _filtrar_formatar_dia(entradas_ext, data_dia, True, "entrada", _formatar_extrato)
        so_ext_sai = _filtrar_formatar_dia(saidas_ext, data_dia, False, "saida", _formatar_extrato)
        conc_ext_sai = _filtrar_formatar_dia(saidas_ext, data_dia, True, "saida", _formatar_extrato)
        so_raz_deb = _filtrar_formatar_dia(debitos_raz, data_dia, False, "debito", _formatar_razao)
        conc_raz_deb = _filtrar_formatar_dia(debitos_raz, data_dia, True, "debito", _formatar_razao)
        so_raz_cred = _filtrar_formatar_dia(creditos_raz, data_dia, False, "credito", _formatar_razao)
        conc_raz_cred = _filtrar_formatar_dia(creditos_raz, data_dia, True, "credito", _formatar_razao)

        # Adicionar aos registros globais (apenas pendentes/divergentes)
        if status_dia == "DIVERGENTE":
            registros_so_extrato.extend(so_ext_ent)
            registros_so_extrato.extend(so_ext_sai)
            registros_so_razao.extend(so_raz_deb)
            registros_so_razao.extend(so_raz_cred)

        dia_info = {
            "data": data_dia,
            "entradas_extrato": round(row["entradas_extrato"], 2),
            "saidas_extrato": round(row["saidas_extrato"], 2),
            "debitos_razao": round(row["debitos_razao"], 2),
            "creditos_razao": round(row["creditos_razao"], 2),
            "dif_entradas": round(dif_entradas, 2),
            "dif_saidas": round(dif_saidas, 2),
            "status": status_dia,
            "conciliado_por_compensacao": conciliado_por_compensacao,
            # Registros NAO conciliados (pendentes) - vermelho
            "so_extrato_entradas": so_ext_ent,
            "so_extrato_saidas": so_ext_sai,
            "so_razao_debitos": so_raz_deb,
            "so_razao_creditos": so_raz_cred,
            # Registros CONCILIADOS (matched) - verde
            "conciliados_extrato_entradas": conc_ext_ent,
            "conciliados_extrato_saidas": conc_ext_sai,
            "conciliados_razao_debitos": conc_raz_deb,
            "conciliados_razao_creditos": conc_raz_cred,
        }
        movimentos_por_dia.append(dia_info)

        if status_dia == "DIVERGENTE":
            dias_divergentes.append(dia_info)
        else:
            dias_conciliados.append(dia_info)

    # ==========================
    # 6.5 SALDO FINAL BATE -> CONSIDERAR TUDO CONCILIADO
    # ==========================
    # Mesmo que dias individuais nao batam (timing de lancamentos entre dias),
    # se o saldo final do periodo (ultima linha de cada base) bate, a conciliacao
    # e considerada OK e todos os dias sao marcados como CONCILIADO (verde).
    if saldo_final_extrato is None:
        saldo_final_extrato = (
            float(df_ext.iloc[-1]["saldo_atual"])
            if len(df_ext) > 0 and "saldo_atual" in df_ext.columns
            else None
        )
    saldo_final_razao = (
        float(df_raz.iloc[-1]["saldo_atual"])
        if len(df_raz) > 0 and "saldo_atual" in df_raz.columns
        else None
    )
    saldo_final_bate = (
        saldo_final_extrato is not None
        and saldo_final_razao is not None
        and abs(saldo_final_extrato - saldo_final_razao) <= THRESHOLD_CONCILIACAO
    )

    if saldo_final_bate:
        logger.info(
            f"[CALC DIFERENCAS BANCO] Saldo final bate (extrato={saldo_final_extrato}, "
            f"razao={saldo_final_razao}) -> marcando todos os dias como CONCILIADO"
        )
        for dia_info in movimentos_por_dia:
            dia_info["status"] = "CONCILIADO"
        dias_conciliados = movimentos_por_dia
        dias_divergentes = []
        registros_so_extrato = []
        registros_so_razao = []

    # ==========================
    # 7. CALCULAR RESUMO
    # ==========================
    total_entradas_extrato = df_merge["entradas_extrato"].sum()
    total_saidas_extrato = df_merge["saidas_extrato"].sum()
    total_debitos_razao = df_merge["debitos_razao"].sum()
    total_creditos_razao = df_merge["creditos_razao"].sum()

    dif_total_entradas = total_debitos_razao - total_entradas_extrato
    dif_total_saidas = total_creditos_razao - total_saidas_extrato

    qtd_dias = len(df_merge)
    qtd_conciliados = len(dias_conciliados)
    qtd_divergentes = len(dias_divergentes)
    qtd_conciliados_por_compensacao = sum(
        1 for dia in movimentos_por_dia if dia.get("conciliado_por_compensacao")
    )

    percentual_conciliacao = (qtd_conciliados / qtd_dias * 100) if qtd_dias > 0 else 0
    situacao = "CONCILIADO" if qtd_divergentes == 0 else "DIVERGENTE"

    resumo = {
        "total_entradas_extrato": round(total_entradas_extrato, 2),
        "total_saidas_extrato": round(total_saidas_extrato, 2),
        "total_debitos_razao": round(total_debitos_razao, 2),
        "total_creditos_razao": round(total_creditos_razao, 2),
        "dif_total_entradas": round(dif_total_entradas, 2),
        "dif_total_saidas": round(dif_total_saidas, 2),
        "situacao": situacao,
        "qtd_dias": qtd_dias,
        "qtd_conciliados": qtd_conciliados,
        "qtd_divergentes": qtd_divergentes,
        "qtd_conciliados_por_compensacao": qtd_conciliados_por_compensacao,
        "percentual_conciliacao": round(percentual_conciliacao, 2),
        "saldo_final_extrato": round(saldo_final_extrato, 2) if saldo_final_extrato is not None else None,
        "saldo_final_razao": round(saldo_final_razao, 2) if saldo_final_razao is not None else None,
        "saldo_final_bate": saldo_final_bate,
        "data_processamento": datetime.now().isoformat(),
    }

    logger.info(f"[CALC DIFERENCAS BANCO] Resumo: {resumo}")
    logger.info(f"[CALC DIFERENCAS BANCO] Registros so extrato: {len(registros_so_extrato)}")
    logger.info(f"[CALC DIFERENCAS BANCO] Registros so razao: {len(registros_so_razao)}")

    return {
        "resumo": resumo,
        "movimentos_por_dia": movimentos_por_dia,
        "dias_divergentes": dias_divergentes,
        "dias_conciliados": dias_conciliados,
        # Registros sem correspondencia (analise detalhada)
        "registros_so_extrato": registros_so_extrato,
        "registros_so_razao": registros_so_razao,
    }
