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


def _fazer_matching_registros(
    df_extrato: pd.DataFrame,
    df_razao: pd.DataFrame,
    data: str,
    dif_entradas: float = 0.0,
    dif_saidas: float = 0.0
) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], bool, bool]:
    """
    Faz o matching de registros entre extrato e razao para uma data especifica.

    Retorna:
        - so_extrato_entradas: Entradas no extrato sem correspondencia no razao (debito)
        - so_extrato_saidas: Saidas no extrato sem correspondencia no razao (credito)
        - so_razao_debitos: Debitos no razao sem correspondencia no extrato
        - so_razao_creditos: Creditos no razao sem correspondencia no extrato
    """
    # Filtrar por data
    ext_dia = df_extrato[df_extrato["data"] == data].copy()
    raz_dia = df_razao[df_razao["data"] == data].copy()

    # Separar entradas/saidas do extrato
    entradas_ext = ext_dia[ext_dia["entrada"] > 0].copy()
    saidas_ext = ext_dia[ext_dia["saida"] > 0].copy()

    # Separar debitos/creditos do razao
    debitos_raz = raz_dia[raz_dia["debito"] > 0].copy()
    creditos_raz = raz_dia[raz_dia["credito"] > 0].copy()

    # Marcar registros como matched
    entradas_ext["matched"] = False
    saidas_ext["matched"] = False
    debitos_raz["matched"] = False
    creditos_raz["matched"] = False

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
        for idx_ext in df_ext.index:
            if df_ext.loc[idx_ext, "matched"]:
                continue
            chave = df_ext.loc[idx_ext, "_doc_key"]
            if not chave:
                continue
            valor_ext = df_ext.loc[idx_ext, col_ext]
            candidatos = df_raz[~df_raz["matched"] & (df_raz["_doc_key"] == chave)]
            for idx_raz in candidatos.index:
                valor_raz = df_raz.loc[idx_raz, col_raz]
                if abs(valor_ext - valor_raz) <= THRESHOLD_CONCILIACAO:
                    df_ext.loc[idx_ext, "matched"] = True
                    df_raz.loc[idx_raz, "matched"] = True
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
                df_ext.loc[pend_ext[pend_ext["_doc_key"] == chave].index, "matched"] = True
                df_raz.loc[pend_raz[pend_raz["_doc_key"] == chave].index, "matched"] = True

    def _match_soma_documentos_relacionados(df_ext: pd.DataFrame, df_raz: pd.DataFrame, col_ext: str, col_raz: str) -> None:
        """
        FASE 2.5: Match por soma de documentos relacionados.
        Ex: Extrato 63616055 (10931.97) vs Razao 63616055 (10665.89) + 63616 (266.08)
        Busca no razao documentos cujo numero base esta contido no numero do extrato.
        """
        pend_ext = df_ext[~df_ext["matched"] & (df_ext["_doc_key"].str.len() > 0)].copy()
        pend_raz = df_raz[~df_raz["matched"] & (df_raz["_doc_key"].str.len() > 0)].copy()
        if pend_ext.empty or pend_raz.empty:
            return

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
            mask_relacionados = pend_raz["_doc_key"].apply(
                lambda x: x == chave_ext or (len(x) >= 3 and chave_ext.startswith(x))
            )
            relacionados = pend_raz[mask_relacionados & ~df_raz.loc[pend_raz.index, "matched"]]

            if relacionados.empty:
                continue

            soma_raz = relacionados[col_raz].sum()
            if abs(valor_ext - soma_raz) <= THRESHOLD_CONCILIACAO:
                df_ext.loc[idx_ext, "matched"] = True
                df_raz.loc[relacionados.index, "matched"] = True
                logger.info(f"[FASE 2.5] Match doc relacionados: {chave_ext} = {valor_ext} vs soma({list(relacionados['_doc_key'].values)}) = {soma_raz}")

    # Preencher chaves de documento (apenas numeros)
    entradas_ext["_doc_key"] = _key_documento(entradas_ext)
    saidas_ext["_doc_key"] = _key_documento(saidas_ext)
    debitos_raz["_doc_key"] = _key_documento(debitos_raz)
    creditos_raz["_doc_key"] = _key_documento(creditos_raz)

    # FASE 1: DATA + DOCUMENTO + VALOR
    _match_exato_doc_valor(entradas_ext, debitos_raz, "entrada", "debito")
    _match_exato_doc_valor(saidas_ext, creditos_raz, "saida", "credito")

    # FASE 2: DATA + DOCUMENTO (soma)
    _match_soma_por_documento(entradas_ext, debitos_raz, "entrada", "debito")
    _match_soma_por_documento(saidas_ext, creditos_raz, "saida", "credito")

    # FASE 2.5: DATA + DOCUMENTOS RELACIONADOS (soma de docs com numero base comum)
    _match_soma_documentos_relacionados(saidas_ext, creditos_raz, "saida", "credito")
    _match_soma_documentos_relacionados(entradas_ext, debitos_raz, "entrada", "debito")

    # FASE 3: DATA + VALOR (fallback)
    for idx_ext in entradas_ext.index:
        if entradas_ext.loc[idx_ext, "matched"]:
            continue
        valor_ext = entradas_ext.loc[idx_ext, "entrada"]

        for idx_raz in debitos_raz.index:
            if debitos_raz.loc[idx_raz, "matched"]:
                continue
            valor_raz = debitos_raz.loc[idx_raz, "debito"]

            if abs(valor_ext - valor_raz) <= THRESHOLD_CONCILIACAO:
                entradas_ext.loc[idx_ext, "matched"] = True
                debitos_raz.loc[idx_raz, "matched"] = True
                break

    for idx_ext in saidas_ext.index:
        if saidas_ext.loc[idx_ext, "matched"]:
            continue
        valor_ext = saidas_ext.loc[idx_ext, "saida"]

        for idx_raz in creditos_raz.index:
            if creditos_raz.loc[idx_raz, "matched"]:
                continue
            valor_raz = creditos_raz.loc[idx_raz, "credito"]

            if abs(valor_ext - valor_raz) <= THRESHOLD_CONCILIACAO:
                saidas_ext.loc[idx_ext, "matched"] = True
                creditos_raz.loc[idx_raz, "matched"] = True
                break

    # ==========================
    # NOTA: Validacao final removida - registros sem match devem permanecer visiveis
    # ==========================
    validacao_final_entradas = False
    validacao_final_saidas = False

    # Coletar registros nao matched
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
        }

    # Registros NAO conciliados (pendentes)
    so_extrato_entradas = [
        _formatar_extrato(row, "entrada")
        for _, row in entradas_ext[~entradas_ext["matched"]].iterrows()
    ]
    so_extrato_saidas = [
        _formatar_extrato(row, "saida")
        for _, row in saidas_ext[~saidas_ext["matched"]].iterrows()
    ]
    so_razao_debitos = [
        _formatar_razao(row, "debito")
        for _, row in debitos_raz[~debitos_raz["matched"]].iterrows()
    ]
    so_razao_creditos = [
        _formatar_razao(row, "credito")
        for _, row in creditos_raz[~creditos_raz["matched"]].iterrows()
    ]

    # Registros CONCILIADOS (matched) - para mostrar em verde
    conciliados_extrato_entradas = [
        _formatar_extrato(row, "entrada")
        for _, row in entradas_ext[entradas_ext["matched"]].iterrows()
    ]
    conciliados_extrato_saidas = [
        _formatar_extrato(row, "saida")
        for _, row in saidas_ext[saidas_ext["matched"]].iterrows()
    ]
    conciliados_razao_debitos = [
        _formatar_razao(row, "debito")
        for _, row in debitos_raz[debitos_raz["matched"]].iterrows()
    ]
    conciliados_razao_creditos = [
        _formatar_razao(row, "credito")
        for _, row in creditos_raz[creditos_raz["matched"]].iterrows()
    ]

    return (
        so_extrato_entradas,
        so_extrato_saidas,
        so_razao_debitos,
        so_razao_creditos,
        validacao_final_entradas,
        validacao_final_saidas,
        # Novos retornos: registros conciliados
        conciliados_extrato_entradas,
        conciliados_extrato_saidas,
        conciliados_razao_debitos,
        conciliados_razao_creditos,
    )


def calcular_diferencas_bancarias(
    df_extrato: pd.DataFrame,
    df_razao: pd.DataFrame
) -> Dict[str, Any]:
    """
    Calcula diferencas entre Extrato Bancario e Razao Contabil AGRUPADO POR DIA.

    Parametros:
    -----------
    df_extrato : pd.DataFrame
        DataFrame normalizado do extrato bancario (FINR470)

    df_razao : pd.DataFrame
        DataFrame normalizado do razao contabil (CTBR400)

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
        return "DIVERGENTE"

    df_merge["status"] = df_merge.apply(classificar_dia, axis=1)

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

    for _, row in df_merge.iterrows():
        data_dia = row["data"]
        dif_entradas = row["dif_entradas"]
        dif_saidas = row["dif_saidas"]

        # Fazer matching detalhado para TODOS os dias (divergentes e conciliados)
        status_dia = row["status"]

        (
            so_ext_ent,
            so_ext_sai,
            so_raz_deb,
            so_raz_cred,
            _validacao_final_ent,
            _validacao_final_sai,
            # Registros conciliados (matched)
            conc_ext_ent,
            conc_ext_sai,
            conc_raz_deb,
            conc_raz_cred,
        ) = _fazer_matching_registros(
            df_ext, df_raz, data_dia,
            dif_entradas=dif_entradas,
            dif_saidas=dif_saidas
        )

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
        "percentual_conciliacao": round(percentual_conciliacao, 2),
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
