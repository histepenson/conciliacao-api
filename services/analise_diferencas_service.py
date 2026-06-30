from typing import List, Dict, Any, Optional
from datetime import datetime, date
import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)


class AnaliseDiferencasService:
    """Gera analise detalhada por codigo (financeiro/contabil)."""

    LIMITE_DIVERGENCIA = 1.00

    def _classificar_tipo(
        self, valor_fin: float, valor_cont: float, diferenca: float
    ) -> str:
        if abs(diferenca) <= self.LIMITE_DIVERGENCIA:
            return "CONCILIADO"
        if valor_fin > 0 and valor_cont == 0:
            return "SO_FINANCEIRO"
        if valor_cont > 0 and valor_fin == 0:
            return "SO_CONTABILIDADE"
        return "DIVERGENTE_VALOR"

    def _status(self, diferenca: float) -> str:
        return "verde" if abs(diferenca) <= self.LIMITE_DIVERGENCIA else "vermelho"

    def _parse_valor(self, valor: object) -> float:
        """Converte valor numerico ou string em formato BR para float."""
        if valor is None:
            return 0.0
        if isinstance(valor, (int, float)):
            return 0.0 if pd.isna(valor) else float(valor)
        s = str(valor).strip()
        if not s or s.lower() in ('nan', 'none', ''):
            return 0.0
        if ',' in s:
            s = s.replace('.', '').replace(',', '.')
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    def _periodo_data_base(self, data_base: Optional[str]) -> Optional[tuple]:
        """Retorna (mes, ano) da data_base para filtrar o periodo analisado."""
        if not data_base:
            return None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(str(data_base).strip(), fmt)
                return (dt.month, dt.year)
            except ValueError:
                continue
        return None

    def _dentro_periodo(self, data_str: str, periodo: Optional[tuple]) -> bool:
        """True se a data pertence ao periodo analisado (ou se nao ha periodo definido)."""
        return periodo is None or self._data_no_periodo(data_str, periodo)

    def _data_no_periodo(self, data_str: str, periodo: tuple) -> bool:
        """Verifica se data_str pertence ao mesmo mes/ano do periodo."""
        if not data_str or data_str == "-":
            return False
        mes, ano = periodo
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%y"):
            try:
                dt = datetime.strptime(str(data_str).strip(), fmt)
                return dt.month == mes and dt.year == ano
            except ValueError:
                continue
        return False

    def processar_analise_detalhada(
        self,
        df_financeiro: pd.DataFrame,
        df_contabilidade_filtrada: pd.DataFrame,
        df_razao_contabil: pd.DataFrame,
        conta_contabil: str,
        df_financeiro_detalhado: Optional[pd.DataFrame] = None,
        df_razao_geral: Optional[pd.DataFrame] = None,
        data_base: Optional[str] = None,
        saldo_ant_map: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Consolida valores por codigo e gera uma analise detalhada financeira.
        """
        logger.info("[ANALISE DETALHADA] Iniciando processamento")

        df_fin = df_financeiro[["codigo", "cliente", "valor"]].copy()
        df_cont = df_contabilidade_filtrada[["codigo", "cliente", "valor"]].copy()
        df_razao = df_razao_contabil.copy()

        fin_agg = df_fin.groupby("codigo", as_index=False).agg(
            nome_fin=("cliente", "first"),
            valor_financeiro=("valor", "sum"),
        )
        cont_agg = df_cont.groupby("codigo", as_index=False).agg(
            nome_cont=("cliente", "first"),
            valor_contabilidade=("valor", "sum"),
        )

        # Criar mapa de codigo -> nome do cliente para uso em todos os lancamentos
        codigo_nome_map: Dict[str, str] = {}
        for _, row in df_fin.iterrows():
            cod = str(row.get("codigo", "")).strip()
            nome = str(row.get("cliente", "")).strip()
            if cod and nome and nome != cod:
                codigo_nome_map[cod] = nome
        for _, row in df_cont.iterrows():
            cod = str(row.get("codigo", "")).strip()
            nome = str(row.get("cliente", "")).strip()
            if cod and nome and nome != cod and cod not in codigo_nome_map:
                codigo_nome_map[cod] = nome

        if not df_razao.empty and "codigo" in df_razao.columns:
            razao_agg = df_razao.groupby("codigo", as_index=False).agg(
                lancamentos_razao=("codigo", "count"),
            )
        else:
            razao_agg = pd.DataFrame(columns=["codigo", "lancamentos_razao"])

        # Mapa de lancamentos no razao geral por ITEMCONTA (para SO_CONTABILIDADE)
        lancamentos_razao_geral: Dict[str, int] = {}
        df_razao_geral_norm = None
        col_itemconta_geral = None
        col_data_geral = None
        col_documento_geral = None
        col_historico_geral = None
        col_debito_geral = None
        col_credito_geral = None
        col_xpartida_geral = None
        col_conta_razao_geral = None
        if df_razao_geral is not None and not df_razao_geral.empty:
            col_itemconta_geral = self._encontrar_coluna(
                df_razao_geral,
                [
                    # No layout usado pela conciliacao de clientes, ITEM CONTA traz o codigo do cliente/fornecedor.
                    "ITEMCONTA",
                    "itemconta",
                    "item_conta",
                    "ITEM CONTA",
                    # COD CL VAL fica como fallback porque em alguns layouts ele pode trazer o codigo.
                    "COD CL VAL",
                    "cod_cl_val",
                    "COD_CL_VAL",
                    "CODCLVAL",
                    "conta_contabil",
                    "Conta Contabil",
                    "conta",
                    "Conta",
                    "CONTA",
                    "conta_contabil_debito",
                    "conta_debito",
                    "ContaContabil",
                ],
            )
            if col_itemconta_geral:
                df_razao_geral_norm = df_razao_geral.copy()
                df_razao_geral_norm["itemconta_normalizado"] = df_razao_geral_norm[col_itemconta_geral].apply(
                    self._normalizar_item_conta_razao
                )

                # Segunda opção: se cod_cl_val existe e é coluna diferente da principal,
                # normaliza também para uso como fallback por linha no matching.
                col_codclval_geral = None
                _candidatas_clval = ["cod_cl_val", "COD CL VAL", "COD_CL_VAL", "CODCLVAL"]
                if col_itemconta_geral not in _candidatas_clval:
                    col_codclval_geral = self._encontrar_coluna(df_razao_geral_norm, _candidatas_clval)
                if col_codclval_geral:
                    df_razao_geral_norm["codclval_normalizado"] = df_razao_geral_norm[col_codclval_geral].apply(
                        self._normalizar_item_conta_razao
                    )

                lancamentos_razao_geral = (
                    df_razao_geral_norm.groupby("itemconta_normalizado").size().to_dict()
                )

                col_data_geral = self._encontrar_coluna(
                    df_razao_geral_norm,
                    [
                        "DATA",
                        "data",
                        "Data",
                        "data_lancamento",
                        "dt_lancamento",
                        "data_movimento",
                        "dt_movimento",
                    ],
                )
                col_documento_geral = self._encontrar_coluna(
                    df_razao_geral_norm,
                    [
                        "LOTE/SUB/DOC/LINHA",
                        "lote_sub_doc_linha",
                        "LOTE SUB DOC LINHA",
                        "documento",
                        "Documento",
                        "DOCUMENTO",
                        "doc",
                        "num_documento",
                        "nr_documento",
                        "numero_documento",
                    ],
                )
                col_historico_geral = self._encontrar_coluna(
                    df_razao_geral_norm,
                    [
                        "HISTORICO",
                        "historico",
                        "Historico",
                        "descricao",
                        "Descricao",
                        "hist_lancamento",
                        "observacao",
                    ],
                )
                col_debito_geral = self._encontrar_coluna(
                    df_razao_geral_norm,
                    [
                        "DEBITO",
                        "debito",
                        "Debito",
                        "DEBITO",
                        "debito",
                        "vlr_debito",
                    ],
                )
                col_credito_geral = self._encontrar_coluna(
                    df_razao_geral_norm,
                    [
                        "CREDITO",
                        "credito",
                        "Credito",
                        "CREDITO",
                        "credito",
                        "vlr_credito",
                    ],
                )
                col_xpartida_geral = self._encontrar_coluna(
                    df_razao_geral_norm,
                    ["xpartida", "XPARTIDA", "partida", "PARTIDA", "contrapartida"],
                )
                col_conta_razao_geral = self._encontrar_coluna(
                    df_razao_geral_norm,
                    ["conta", "CONTA"],
                )
                col_ct5_desc_geral = self._encontrar_coluna(
                    df_razao_geral_norm,
                    ["ct5_desc", "CT5_DESC"],
                )

        df_merge = fin_agg.merge(cont_agg, on="codigo", how="outer")
        if not razao_agg.empty:
            df_merge = df_merge.merge(razao_agg, on="codigo", how="left")
        else:
            df_merge["lancamentos_razao"] = 0

        df_merge["valor_financeiro"] = df_merge["valor_financeiro"].fillna(0.0).abs()
        df_merge["valor_contabilidade"] = df_merge["valor_contabilidade"].fillna(0.0).abs()
        df_merge["lancamentos_razao"] = (
            df_merge["lancamentos_razao"].fillna(0).astype(int)
        )

        df_merge["nome"] = df_merge["nome_fin"].fillna(df_merge["nome_cont"])
        df_merge["diferenca"] = (
            df_merge["valor_financeiro"] - df_merge["valor_contabilidade"]
        )

        periodo = self._periodo_data_base(data_base)
        logger.info("[ANALISE DETALHADA] Periodo analisado: %s", periodo)

        # financeiro_match_map: usado para marcar correspondencia em lancamentos do razao
        # Filtra apenas entradas do periodo analisado (mes/ano da data_base)
        financeiro_match_map: Dict[tuple[str, str], List[float]] = {}
        # valor_fin_periodo_map: soma do financeiro apenas no periodo, por codigo (para status verde/vermelho)
        valor_fin_periodo_map: Dict[str, float] = {}
        if df_financeiro_detalhado is not None and not df_financeiro_detalhado.empty:
            if "codigo" in df_financeiro_detalhado.columns:
                df_fin_match = df_financeiro_detalhado.copy()
                df_fin_match["codigo"] = df_fin_match["codigo"].astype(str).str.strip()
                if "data_emissao" in df_fin_match.columns:
                    df_fin_match["data_match"] = df_fin_match["data_emissao"].apply(
                        self._formatar_data
                    )
                else:
                    df_fin_match["data_match"] = ""
                df_fin_match["valor_match"] = (
                    pd.to_numeric(df_fin_match.get("valor"), errors="coerce")
                    .fillna(0.0)
                    .astype(float)
                )
                for _, row_fin in df_fin_match.iterrows():
                    data_m = row_fin.get("data_match", "")
                    cod = row_fin.get("codigo", "")
                    val = float(row_fin.get("valor_match", 0.0))
                    # Match map: so entradas do periodo
                    if periodo is None or self._data_no_periodo(data_m, periodo):
                        key = (cod, data_m)
                        financeiro_match_map.setdefault(key, []).append(val)
                        valor_fin_periodo_map[cod] = valor_fin_periodo_map.get(cod, 0.0) + val

        # Snapshot imutavel do mapa financeiro (antes de qualquer pop) para determinar
        # tem_correspondencia por entrada do razao (chave = codigo+data, independente do valor)
        financeiro_match_map_snap: Dict[tuple, List[float]] = {
            k: list(v) for k, v in financeiro_match_map.items()
        }

        def _tem_match_financeiro(codigo: str, data_str: str, valor: float) -> bool:
            key = (codigo, data_str)
            valores = financeiro_match_map.get(key)
            if not valores:
                return False
            for i, v in enumerate(valores):
                if abs(v - valor) <= 0.01:
                    valores.pop(i)
                    return True
            return False

        def _correspondencia_financeiro(codigo: str, data_str: str, valor: float):
            """
            Retorna (tem_correspondencia, valor_financeiro_match) usando o snapshot original.

            Lancamentos do razao fora do periodo analisado nao tem como ter correspondencia
            no financeiro do periodo (financeiro_match_map so cobre o periodo analisado) --
            nesses casos retorna (None, None) para o frontend mostrar neutro (sem cor),
            em vez de vermelho (mesma regra ja aplicada para os titulos do financeiro).
            """
            if periodo is not None and not self._data_no_periodo(data_str, periodo):
                return None, None
            valores_snap = financeiro_match_map_snap.get((codigo, data_str), [])
            if not valores_snap:
                return False, None
            closest = min(valores_snap, key=lambda v: abs(v - valor))
            return True, round(closest, 2)

        analises: List[Dict[str, Any]] = []
        for row in df_merge.to_dict("records"):
            codigo = str(row.get("codigo", "")).strip()
            valor_fin = float(row.get("valor_financeiro", 0.0))
            valor_cont = float(row.get("valor_contabilidade", 0.0))
            diferenca = float(row.get("diferenca", 0.0))

            # Para status (verde/vermelho): usa apenas o financeiro do periodo analisado
            if periodo is not None and codigo in valor_fin_periodo_map:
                valor_fin_periodo = valor_fin_periodo_map[codigo]
                diferenca_periodo = valor_fin_periodo - valor_cont
            else:
                diferenca_periodo = diferenca

            tipo = self._classificar_tipo(valor_fin, valor_cont, diferenca)
            status = self._status(diferenca_periodo)

            # A coluna exibida como "Fornecedor" no frontend deve mostrar o codigo.
            nome_exibicao = codigo or str(row.get("nome") or "").strip()

            lancamentos_razao = int(row.get("lancamentos_razao", 0))
            lancamentos_razao_detalhes: List[Dict[str, Any]] = []
            lancamentos_razao_todos: List[Dict[str, Any]] = []
            lancamentos_financeiro_detalhes: List[Dict[str, Any]] = []
            lancamentos_razao_sem_financeiro: List[Dict[str, Any]] = []
            registros_match_financeiro: List[Dict[str, Any]] = []
            registros_match_contabilidade: List[Dict[str, Any]] = []
            sem_lancamentos_razao = False
            nota_razao = ""

            codigo_normalizado = self._normalizar_codigo_numerico(codigo)
            matches_razao_count = 0
            matches_item_all = pd.DataFrame()
            if df_razao_geral_norm is not None and col_itemconta_geral:
                matches_item_all = self._filtrar_razao_por_codigo(df_razao_geral_norm, codigo_normalizado)
                matches_razao_count = int(len(matches_item_all))
                lancamentos_razao = matches_razao_count
                if (
                    matches_razao_count == 0
                    and abs(diferenca) > 0.01
                    and tipo == "SO_CONTABILIDADE"
                ):
                    sem_lancamentos_razao = True
                    nota_razao = "Sem lan?amentos no per?odo."

                for _, r in matches_item_all.iterrows():
                    valor_debito = 0.0
                    valor_credito = 0.0
                    if col_debito_geral:
                        try:
                            val = r.get(col_debito_geral, 0)
                            if pd.notna(val):
                                valor_debito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_debito = 0.0
                    if col_credito_geral:
                        try:
                            val = r.get(col_credito_geral, 0)
                            if pd.notna(val):
                                valor_credito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_credito = 0.0

                    if abs(valor_debito) > 0:
                        valor_lancamento = abs(valor_debito)
                        tipo_lancamento = "D"
                    elif abs(valor_credito) > 0:
                        valor_lancamento = abs(valor_credito)
                        tipo_lancamento = "C"
                    else:
                        continue

                    item_conta = (
                        str(r.get(col_itemconta_geral, ""))
                        if col_itemconta_geral
                        else ""
                    )
                    data_lanc = self._formatar_data(
                        r.get(col_data_geral, "") if col_data_geral else "", periodo
                    )
                    nome_cliente = codigo_nome_map.get(codigo, "")

                    lancamentos_razao_todos.append(
                        {
                            "conta_origem": item_conta,
                            "descricao_conta": nome_cliente if nome_cliente else "",
                            "valor": round(valor_lancamento, 2),
                            "tipo_lancamento": tipo_lancamento,
                            "debito": round(valor_debito, 2),
                            "credito": round(valor_credito, 2),
                            "xpartida": str(r.get(col_xpartida_geral, "")) if col_xpartida_geral else "",
                            "conta": str(r.get(col_conta_razao_geral, "")) if col_conta_razao_geral else "",
                            "data_lancamento": data_lanc,
                            "documento": str(r.get(col_documento_geral, ""))
                            if col_documento_geral
                            else "",
                            "historico": str(r.get(col_historico_geral, ""))
                            if col_historico_geral
                            else "",
                            "tipo_movimento": "NAO_IDENTIFICADO",
                            "ct5_desc": str(r.get(col_ct5_desc_geral, "")) if col_ct5_desc_geral else "",
                            "dentro_periodo": self._dentro_periodo(data_lanc, periodo),
                        }
                    )
            if tipo == "SO_CONTABILIDADE" and lancamentos_razao_geral:
                codigo_normalizado = self._normalizar_codigo_numerico(codigo)
                if df_razao_geral_norm is not None and col_itemconta_geral:
                    matches_item = df_razao_geral_norm[
                        df_razao_geral_norm["itemconta_normalizado"]
                        == codigo_normalizado
                    ]
                    for _, r in matches_item.iterrows():
                        valor_debito = 0.0
                        valor_credito = 0.0
                        if col_debito_geral:
                            try:
                                val = r.get(col_debito_geral, 0)
                                if pd.notna(val):
                                    valor_debito = self._parse_valor(val)
                            except (ValueError, TypeError):
                                valor_debito = 0.0
                        if col_credito_geral:
                            try:
                                val = r.get(col_credito_geral, 0)
                                if pd.notna(val):
                                    valor_credito = self._parse_valor(val)
                            except (ValueError, TypeError):
                                valor_credito = 0.0

                        if abs(valor_debito) > 0:
                            valor_lancamento = abs(valor_debito)
                            tipo_lancamento = "D"
                        elif abs(valor_credito) > 0:
                            valor_lancamento = abs(valor_credito)
                            tipo_lancamento = "C"
                        else:
                            valor_lancamento = 0.0
                            tipo_lancamento = ""
                        item_conta = (
                            str(r.get(col_itemconta_geral, ""))
                            if col_itemconta_geral
                            else ""
                        )

                        if valor_lancamento <= 0:
                            continue

                        data_lanc = self._formatar_data(
                            r.get(col_data_geral, "") if col_data_geral else "", periodo
                        )
                        tem_corr_det, vlr_fin_det = _correspondencia_financeiro(
                            codigo, data_lanc, valor_lancamento
                        )
                        if _tem_match_financeiro(codigo, data_lanc, valor_lancamento):
                            continue

                        # Obter nome do cliente do mapa
                        nome_cliente = codigo_nome_map.get(codigo, "")

                        lancamentos_razao_detalhes.append(
                            {
                                "conta_origem": item_conta,
                                "descricao_conta": nome_cliente if nome_cliente else "",
                                "valor": round(valor_lancamento, 2),
                                "tipo_lancamento": tipo_lancamento,
                                "debito": round(valor_debito, 2),
                                "credito": round(valor_credito, 2),
                                "xpartida": str(r.get(col_xpartida_geral, "")) if col_xpartida_geral else "",
                                "conta": str(r.get(col_conta_razao_geral, "")) if col_conta_razao_geral else "",
                                "data_lancamento": data_lanc,
                                "documento": str(r.get(col_documento_geral, ""))
                                if col_documento_geral
                                else "",
                                "historico": str(r.get(col_historico_geral, ""))
                                if col_historico_geral
                                else "",
                                "tipo_movimento": "NAO_IDENTIFICADO",
                                "ct5_desc": str(r.get(col_ct5_desc_geral, "")) if col_ct5_desc_geral else "",
                                "tem_correspondencia": tem_corr_det,
                                "valor_financeiro_match": vlr_fin_det,
                                "dentro_periodo": self._dentro_periodo(data_lanc, periodo),
                            }
                        )

                lancamentos_razao = int(
                    lancamentos_razao_geral.get(codigo_normalizado, 0)
                )

                # Em SO_CONTABILIDADE: tenta selecionar subconjunto que explica a diferenca.
                # Se nao encontrar match exato, mostra TODOS os lancamentos encontrados.
                _filtrados = self._selecionar_por_diferenca(
                    lancamentos_razao_detalhes, diferenca, "D"
                )
                lancamentos_razao_detalhes = _filtrados if _filtrados else lancamentos_razao_detalhes

            if tipo == "DIVERGENTE_VALOR" and df_razao_geral_norm is not None and col_itemconta_geral:
                codigo_norm_div = self._normalizar_codigo_numerico(codigo)
                matches_div = self._filtrar_razao_por_codigo(df_razao_geral_norm, codigo_norm_div)
                logger.warning("[DIV_VALOR] codigo=%s norm=%s matches=%d", codigo, codigo_norm_div, len(matches_div))
                _div_skipped = 0
                for _, r in matches_div.iterrows():
                    valor_debito = 0.0
                    valor_credito = 0.0
                    if col_debito_geral:
                        try:
                            val = r.get(col_debito_geral, 0)
                            if pd.notna(val):
                                valor_debito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_debito = 0.0
                    if col_credito_geral:
                        try:
                            val = r.get(col_credito_geral, 0)
                            if pd.notna(val):
                                valor_credito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_credito = 0.0

                    if abs(valor_debito) > 0:
                        valor_lancamento = abs(valor_debito)
                        tipo_lancamento = "D"
                    elif abs(valor_credito) > 0:
                        valor_lancamento = abs(valor_credito)
                        tipo_lancamento = "C"
                    else:
                        continue

                    if valor_lancamento <= 0:
                        continue

                    item_conta = (
                        str(r.get(col_itemconta_geral, ""))
                        if col_itemconta_geral
                        else ""
                    )
                    data_lanc = self._formatar_data(
                        r.get(col_data_geral, "") if col_data_geral else "", periodo
                    )
                    tem_corr_div, vlr_fin_div = _correspondencia_financeiro(
                        codigo, data_lanc, valor_lancamento
                    )
                    if _tem_match_financeiro(codigo, data_lanc, valor_lancamento):
                        _div_skipped += 1
                        logger.warning("[DIV_VALOR] SKIP exact match: codigo=%s data=%s valor=%.2f", codigo, data_lanc, valor_lancamento)
                        continue
                    nome_cliente = codigo_nome_map.get(codigo, "")
                    lancamentos_razao_detalhes.append({
                        "conta_origem": item_conta,
                        "descricao_conta": nome_cliente if nome_cliente else "",
                        "valor": round(valor_lancamento, 2),
                        "tipo_lancamento": tipo_lancamento,
                        "debito": round(valor_debito, 2),
                        "credito": round(valor_credito, 2),
                        "xpartida": str(r.get(col_xpartida_geral, "")) if col_xpartida_geral else "",
                        "conta": str(r.get(col_conta_razao_geral, "")) if col_conta_razao_geral else "",
                        "data_lancamento": data_lanc,
                        "documento": str(r.get(col_documento_geral, "")) if col_documento_geral else "",
                        "historico": str(r.get(col_historico_geral, "")) if col_historico_geral else "",
                        "tipo_movimento": "NAO_IDENTIFICADO",
                        "ct5_desc": str(r.get(col_ct5_desc_geral, "")) if col_ct5_desc_geral else "",
                        "tem_correspondencia": tem_corr_div,
                        "valor_financeiro_match": vlr_fin_div,
                        "dentro_periodo": self._dentro_periodo(data_lanc, periodo),
                    })
                logger.warning("[DIV_VALOR] codigo=%s: %d adicionados, %d skipped (match exato), detalhes=%d", codigo, len(matches_div) - _div_skipped, _div_skipped, len(lancamentos_razao_detalhes))

            if (
                valor_cont > valor_fin
                and tipo != "DIVERGENTE_VALOR"
                and df_razao_geral_norm is not None
                and col_itemconta_geral
            ):
                codigo_normalizado = self._normalizar_codigo_numerico(codigo)
                matches_item = self._filtrar_razao_por_codigo(df_razao_geral_norm, codigo_normalizado)
                for _, r in matches_item.iterrows():
                    valor_debito = 0.0
                    valor_credito = 0.0
                    if col_debito_geral:
                        try:
                            val = r.get(col_debito_geral, 0)
                            if pd.notna(val):
                                valor_debito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_debito = 0.0
                    if col_credito_geral:
                        try:
                            val = r.get(col_credito_geral, 0)
                            if pd.notna(val):
                                valor_credito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_credito = 0.0

                    if abs(valor_debito) > 0:
                        valor_lancamento = abs(valor_debito)
                        tipo_lancamento = "D"
                    elif abs(valor_credito) > 0:
                        valor_lancamento = abs(valor_credito)
                        tipo_lancamento = "C"
                    else:
                        valor_lancamento = 0.0
                        tipo_lancamento = ""
                    if valor_lancamento <= 0:
                        continue

                    data_lanc = self._formatar_data(
                        r.get(col_data_geral, "") if col_data_geral else "", periodo
                    )
                    tem_corr_sf, vlr_fin_sf = _correspondencia_financeiro(
                        codigo, data_lanc, valor_lancamento
                    )
                    if _tem_match_financeiro(codigo, data_lanc, valor_lancamento):
                        continue

                    item_conta = (
                        str(r.get(col_itemconta_geral, ""))
                        if col_itemconta_geral
                        else ""
                    )
                    # Obter nome do cliente do mapa
                    nome_cliente = codigo_nome_map.get(codigo, "")

                    lancamentos_razao_sem_financeiro.append(
                        {
                            "conta_origem": item_conta,
                            "descricao_conta": nome_cliente if nome_cliente else "",
                            "valor": round(valor_lancamento, 2),
                            "tipo_lancamento": tipo_lancamento,
                            "debito": round(valor_debito, 2),
                            "credito": round(valor_credito, 2),
                            "xpartida": str(r.get(col_xpartida_geral, "")) if col_xpartida_geral else "",
                            "conta": str(r.get(col_conta_razao_geral, "")) if col_conta_razao_geral else "",
                            "data_lancamento": data_lanc,
                            "documento": str(r.get(col_documento_geral, ""))
                            if col_documento_geral
                            else "",
                            "historico": str(r.get(col_historico_geral, ""))
                            if col_historico_geral
                            else "",
                            "tipo_movimento": "NAO_IDENTIFICADO",
                            "ct5_desc": str(r.get(col_ct5_desc_geral, "")) if col_ct5_desc_geral else "",
                            "tem_correspondencia": tem_corr_sf,
                            "valor_financeiro_match": vlr_fin_sf,
                            "dentro_periodo": self._dentro_periodo(data_lanc, periodo),
                        }
                    )

                # Em divergencia contabilidade > financeiro, tenta selecionar subconjunto exato;
                # se nao encontrar, exibe todos os lancamentos encontrados (comportamento igual ao bloco valor_cont < valor_fin)
                _sel_sf = self._selecionar_por_diferenca(lancamentos_razao_sem_financeiro, diferenca, "D")
                lancamentos_razao_sem_financeiro = _sel_sf if _sel_sf else lancamentos_razao_sem_financeiro

            # Lookup de NFs presentes no razao para este codigo (usado no bloco SO_FINANCEIRO)
            _NF_PAT = re.compile(r'\bNF\s*(\d+)', re.IGNORECASE)
            razao_nf_valor_set: set = set()
            for _lz in lancamentos_razao_todos:
                _hist = str(_lz.get("historico", ""))
                _m = _NF_PAT.search(_hist)
                if _m:
                    razao_nf_valor_set.add((_m.group(1), round(float(_lz.get("valor", 0) or 0), 2)))

            if tipo == "SO_FINANCEIRO" and df_financeiro_detalhado is not None and not df_financeiro_detalhado.empty:
                if "codigo" in df_financeiro_detalhado.columns:
                    matches_fin = df_financeiro_detalhado[
                        df_financeiro_detalhado["codigo"].astype(str) == codigo
                    ]
                else:
                    matches_fin = pd.DataFrame()

                for _, r in matches_fin.iterrows():
                    cliente = str(r.get("cliente", "")).strip()
                    valor_fin_det = float(r.get("valor", 0) or 0)
                    data_emissao = r.get("data_emissao", "")
                    prf_numero = r.get("numero_documento", r.get("prf_numero", ""))
                    parcela = r.get("parcela", "")
                    tipo_titulo = r.get("tipo_titulo", "")

                    doc_parts = []
                    prf_str = ""
                    parcela_str = ""
                    def _normalizar_doc(valor: object) -> str:
                        if valor in [None, ""] or pd.isna(valor):
                            return ""
                        s = str(valor).strip()
                        s_clean = s.strip("- ")
                        if re.search(r"[A-Za-z]", s_clean):
                            return s_clean
                        digits = re.sub(r"\D+", "", s_clean)
                        if len(digits) == 9:
                            return digits
                        return s_clean

                    if prf_numero not in [None, ""] and not pd.isna(prf_numero):
                        prf_str = _normalizar_doc(prf_numero)
                        if prf_str:
                            doc_parts.append(prf_str)
                    if parcela not in [None, ""] and not pd.isna(parcela):
                        parcela_str = _normalizar_doc(parcela)
                        if parcela_str and parcela_str != prf_str:
                            if prf_str and parcela_str in prf_str:
                                pass
                            else:
                                doc_parts.append(parcela_str)
                    documento = "-".join(doc_parts)

                    tp_str = ""
                    if tipo_titulo not in [None, ""] and not pd.isna(tipo_titulo):
                        tp_str = str(tipo_titulo).strip()

                    # Entradas fora do periodo analisado nao tem correspondencia esperada no razao
                    # (o razao so cobre o periodo fechado). Nesses casos, nao marcar como vermelho.
                    _data_emissao_fmt = self._formatar_data(data_emissao, periodo)
                    _dentro_periodo_fin = not (periodo and not self._data_no_periodo(_data_emissao_fmt, periodo))
                    if not _dentro_periodo_fin:
                        tem_corr = None  # fora do periodo -> frontend: neutro (sem cor)
                    else:
                        tem_corr = bool(prf_str and any(
                            nf == prf_str and abs(v - valor_fin_det) <= 0.01
                            for nf, v in razao_nf_valor_set
                        ))

                    lancamentos_financeiro_detalhes.append(
                        {
                            "conta_origem": codigo,
                            "descricao_conta": cliente,
                            "valor": round(valor_fin_det, 2),
                            "tipo_lancamento": "",
                            "data_lancamento": self._formatar_data(data_emissao, periodo),
                            "documento": documento,
                            "tipo_titulo": tp_str,
                            "historico": "",
                            "tipo_movimento": "NAO_IDENTIFICADO",
                            "tem_correspondencia": tem_corr,
                            "dentro_periodo": _dentro_periodo_fin,
                        }
                    )

            if (
                valor_cont < valor_fin
                and df_razao_geral_norm is not None
                and col_itemconta_geral
            ):
                codigo_normalizado = self._normalizar_codigo_numerico(codigo)
                matches_item = self._filtrar_razao_por_codigo(df_razao_geral_norm, codigo_normalizado)
                lancamentos_razao_tmp: List[Dict[str, Any]] = []
                for _, r in matches_item.iterrows():
                    valor_debito = 0.0
                    valor_credito = 0.0
                    if col_debito_geral:
                        try:
                            val = r.get(col_debito_geral, 0)
                            if pd.notna(val):
                                valor_debito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_debito = 0.0
                    if col_credito_geral:
                        try:
                            val = r.get(col_credito_geral, 0)
                            if pd.notna(val):
                                valor_credito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_credito = 0.0

                    # Coleta debito OU credito (contas a receber usam D; contas a pagar usam C)
                    if abs(valor_debito) > 0:
                        valor_lancamento = abs(valor_debito)
                        tipo_lanc = "D"
                    elif abs(valor_credito) > 0:
                        valor_lancamento = abs(valor_credito)
                        tipo_lanc = "C"
                    else:
                        continue

                    data_lanc = self._formatar_data(
                        r.get(col_data_geral, "") if col_data_geral else "", periodo
                    )
                    tem_corr_tmp, vlr_fin_tmp = _correspondencia_financeiro(
                        codigo, data_lanc, valor_lancamento
                    )
                    if _tem_match_financeiro(codigo, data_lanc, valor_lancamento):
                        continue

                    item_conta = (
                        str(r.get(col_itemconta_geral, ""))
                        if col_itemconta_geral
                        else ""
                    )
                    nome_cliente = codigo_nome_map.get(codigo, "")

                    lancamentos_razao_tmp.append(
                        {
                            "conta_origem": item_conta,
                            "descricao_conta": nome_cliente if nome_cliente else "",
                            "valor": round(valor_lancamento, 2),
                            "tipo_lancamento": tipo_lanc,
                            "debito": round(valor_debito, 2),
                            "credito": round(valor_credito, 2),
                            "xpartida": str(r.get(col_xpartida_geral, "")) if col_xpartida_geral else "",
                            "conta": str(r.get(col_conta_razao_geral, "")) if col_conta_razao_geral else "",
                            "data_lancamento": data_lanc,
                            "documento": str(r.get(col_documento_geral, ""))
                            if col_documento_geral
                            else "",
                            "historico": str(r.get(col_historico_geral, ""))
                            if col_historico_geral
                            else "",
                            "tipo_movimento": "NAO_IDENTIFICADO",
                            "ct5_desc": str(r.get(col_ct5_desc_geral, "")) if col_ct5_desc_geral else "",
                            "tem_correspondencia": tem_corr_tmp,
                            "valor_financeiro_match": vlr_fin_tmp,
                            "dentro_periodo": self._dentro_periodo(data_lanc, periodo),
                        }
                    )

                # Tenta selecionar subconjunto por debito (contas a receber) ou credito (contas a pagar)
                _filtrado = self._selecionar_por_diferenca(lancamentos_razao_tmp, diferenca, "D")
                if not _filtrado:
                    _filtrado = self._selecionar_por_diferenca(lancamentos_razao_tmp, diferenca, "C")
                lancamentos_razao_sem_financeiro = _filtrado if _filtrado else lancamentos_razao_tmp

            # Registros individuais de ambas as bases (para todos os tipos)
            status_registro = "conciliado" if tipo == "CONCILIADO" else "divergente"

            # Financeiro detalhado
            if df_financeiro_detalhado is not None and not df_financeiro_detalhado.empty:
                if "codigo" in df_financeiro_detalhado.columns:
                    matches_fin_det = df_financeiro_detalhado[
                        df_financeiro_detalhado["codigo"].astype(str).str.strip() == codigo
                    ]

                    # Para DIVERGENTE_VALOR: construir pool de valores do razao para matching individual.
                    # Cada registro financeiro sera comparado ao razao por valor para identificar
                    # quais titulos tem correspondencia e quais sao os "extras" causadores da diferenca.
                    razao_valores_pool: list = []
                    if tipo == "DIVERGENTE_VALOR" and df_razao_geral_norm is not None and col_itemconta_geral:
                        codigo_norm_match = self._normalizar_codigo_numerico(codigo)
                        matches_razao_match = self._filtrar_razao_por_codigo(df_razao_geral_norm, codigo_norm_match)
                        for _, rz in matches_razao_match.iterrows():
                            v_d = 0.0
                            v_c = 0.0
                            if col_debito_geral:
                                try:
                                    val = rz.get(col_debito_geral, 0)
                                    if pd.notna(val):
                                        v_d = self._parse_valor(val)
                                except (ValueError, TypeError):
                                    pass
                            if col_credito_geral:
                                try:
                                    val = rz.get(col_credito_geral, 0)
                                    if pd.notna(val):
                                        v_c = self._parse_valor(val)
                                except (ValueError, TypeError):
                                    pass
                            v = abs(v_d) if abs(v_d) > 0 else abs(v_c)
                            if v > 0:
                                razao_valores_pool.append(round(v, 2))

                    for _, r in matches_fin_det.iterrows():
                        prf = r.get("numero_documento", r.get("prf_numero", ""))
                        parcela_val = r.get("parcela", "")
                        doc_parts = []
                        if prf not in [None, ""] and not pd.isna(prf):
                            doc_parts.append(str(prf).strip())
                        if parcela_val not in [None, ""] and not pd.isna(parcela_val):
                            p_str = str(parcela_val).strip()
                            if p_str and p_str not in doc_parts:
                                doc_parts.append(p_str)
                        tp_val = r.get("tipo_titulo", "")
                        tp_str2 = ""
                        if tp_val not in [None, ""] and not pd.isna(tp_val):
                            tp_str2 = str(tp_val).strip()

                        valor_fin_rec = round(float(r.get("valor", 0) or 0), 2)

                        # Titulo fora do periodo analisado: nao tem como ter correspondencia
                        # esperada no razao do periodo -- deixa neutro (sem cor) em vez de
                        # avaliar/marcar como divergente.
                        _data_emissao_rec_fmt = self._formatar_data(r.get("data_emissao", ""), periodo)
                        _fora_do_periodo_rec = periodo is not None and not self._data_no_periodo(
                            _data_emissao_rec_fmt, periodo
                        )

                        # Matching individual por valor (apenas para DIVERGENTE_VALOR)
                        tem_correspondencia: Optional[bool] = None
                        if not _fora_do_periodo_rec and tipo == "DIVERGENTE_VALOR" and razao_valores_pool is not None:
                            for i, rv in enumerate(razao_valores_pool):
                                if abs(rv - valor_fin_rec) <= 0.01:
                                    razao_valores_pool.pop(i)
                                    tem_correspondencia = True
                                    break
                            if tem_correspondencia is None:
                                tem_correspondencia = False

                        status_rec = (
                            "conciliado" if tem_correspondencia is True
                            else "divergente" if tem_correspondencia is False
                            else status_registro
                        )

                        entry: Dict[str, Any] = {
                            "descricao": str(r.get("cliente", "")).strip(),
                            "valor": valor_fin_rec,
                            "data_emissao": self._formatar_data(r.get("data_emissao", ""), periodo),
                            "documento": "-".join(doc_parts),
                            "tipo_titulo": tp_str2,
                            "status": status_rec,
                            "dentro_periodo": not _fora_do_periodo_rec,
                        }
                        if tem_correspondencia is not None:
                            entry["tem_correspondencia"] = tem_correspondencia

                        registros_match_financeiro.append(entry)

            # Contabilidade
            matches_cont_det = df_cont[df_cont["codigo"].astype(str).str.strip() == codigo]
            for _, r in matches_cont_det.iterrows():
                registros_match_contabilidade.append({
                    "descricao": str(r.get("cliente", "")).strip(),
                    "valor": round(float(r.get("valor", 0) or 0), 2),
                    "status": status_registro,
                })

            lancamentos_razao_detalhes = self._aglutinar_por_nf(lancamentos_razao_detalhes)
            lancamentos_razao_sem_financeiro = self._aglutinar_por_nf(lancamentos_razao_sem_financeiro)
            lancamentos_razao_todos = self._aglutinar_por_nf(lancamentos_razao_todos)

            lancamentos_financeiro_detalhes.sort(
                key=lambda x: self._parse_data_ordenacao(x.get("data_lancamento", ""))
            )

            saldo_anterior = saldo_ant_map.get(codigo) if saldo_ant_map else None

            analises.append(
                {
                    "codigo": codigo,
                    "nome": nome_exibicao,
                    "conta_contabil": conta_contabil,
                    "valor_financeiro": round(valor_fin, 2),
                    "valor_contabilidade": round(valor_cont, 2),
                    "diferenca": round(diferenca, 2),
                    "tipo_diferenca": tipo,
                    "status": status,
                    "saldo_anterior": saldo_anterior,
                    "lancamentos_razao": lancamentos_razao,
                    "lancamentos_razao_detalhes": (
                        lancamentos_razao_detalhes
                        if lancamentos_razao_detalhes
                        else (
                            lancamentos_razao_sem_financeiro
                            if lancamentos_razao_sem_financeiro
                            else lancamentos_razao_todos
                        )
                    ),
                    "lancamentos_financeiro_detalhes": lancamentos_financeiro_detalhes,
                    "registros_match_financeiro": registros_match_financeiro,
                    "registros_match_contabilidade": registros_match_contabilidade,
                    "sem_lancamentos_razao": sem_lancamentos_razao,
                    "nota_razao": nota_razao,
                }
            )

        analises.sort(key=lambda x: (x["status"] == "verde", abs(x["diferenca"])))

        logger.info(f"[ANALISE DETALHADA] Total de analises geradas: {len(analises)}")
        return analises

    def _parse_data_ordenacao(self, data_str: str) -> str:
        """Converte data para YYYY-MM-DD para ordenacao correta."""
        if not data_str or data_str == "-":
            return "9999-99-99"
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(str(data_str).strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return "9999-99-99"

    def _aglutinar_por_nf(self, lancamentos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aglutina lancamentos do razao por NF (extraido do historico) e tipo D/C."""
        if not lancamentos:
            return lancamentos

        NF_PATTERN = re.compile(r'\bNF\s*(\d+)', re.IGNORECASE)
        agrupados: Dict[tuple, Dict[str, Any]] = {}
        sem_nf: List[Dict[str, Any]] = []

        for lanc in lancamentos:
            historico = str(lanc.get("historico", ""))
            m = NF_PATTERN.search(historico)
            if not m:
                sem_nf.append(lanc)
                continue
            nf = m.group(1)
            tipo = lanc.get("tipo_lancamento", "")
            chave = (nf, tipo)
            if chave not in agrupados:
                agrupados[chave] = {
                    "conta_origem": lanc.get("conta_origem", ""),
                    "descricao_conta": lanc.get("descricao_conta", ""),
                    "valor": 0.0,
                    "tipo_lancamento": tipo,
                    "debito": 0.0,
                    "credito": 0.0,
                    "xpartida": lanc.get("xpartida", ""),
                    "conta": lanc.get("conta", ""),
                    "data_lancamento": lanc.get("data_lancamento", ""),
                    "documento": nf,
                    "historico": lanc.get("historico", ""),
                    "tipo_movimento": lanc.get("tipo_movimento", ""),
                    "ct5_desc": lanc.get("ct5_desc", ""),
                    # tem_correspondencia: True se qualquer entrada do grupo tiver codigo+data
                    # no financeiro (mas valor diferente); False se nenhuma tiver.
                    "tem_correspondencia": lanc.get("tem_correspondencia"),
                    "valor_financeiro_match": lanc.get("valor_financeiro_match"),
                    # dentro_periodo: True se qualquer entrada do grupo for do periodo analisado
                    "dentro_periodo": lanc.get("dentro_periodo", True),
                }
            else:
                # Propagar tem_correspondencia: True tem prioridade sobre False/None
                if lanc.get("tem_correspondencia") is True:
                    agrupados[chave]["tem_correspondencia"] = True
                    agrupados[chave]["valor_financeiro_match"] = lanc.get("valor_financeiro_match")
                if lanc.get("dentro_periodo", True):
                    agrupados[chave]["dentro_periodo"] = True
            agrupados[chave]["valor"] = round(
                agrupados[chave]["valor"] + float(lanc.get("valor", 0) or 0), 2
            )
            agrupados[chave]["debito"] = round(
                agrupados[chave]["debito"] + float(lanc.get("debito", 0) or 0), 2
            )
            agrupados[chave]["credito"] = round(
                agrupados[chave]["credito"] + float(lanc.get("credito", 0) or 0), 2
            )

        return list(agrupados.values()) + sem_nf

    def gerar_resumo_analise(self, analises: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(analises)
        conciliados = sum(1 for a in analises if a.get("status") == "verde")
        divergentes = total - conciliados
        percentual = (conciliados / total * 100) if total else 0.0

        resumo = {
            "total_registros": total,
            "total": total,
            "conciliados": conciliados,
            "divergentes": divergentes,
            "percentual_conciliacao": round(percentual, 2),
            "percentual": round(percentual, 2),
        }
        logger.info(f"[ANALISE DETALHADA] Resumo: {resumo}")
        return resumo

    # ==================================================
    # ANALISE PROFUNDA SO_CONTABILIDADE
    # ==================================================

    def _normalizar_codigo_razao(self, valor: object) -> str:
        """
        Normaliza codigo do razao geral (COD CL VAL) para formato {base}{loja}.

        Suporta:
        - '11419013 -0002-NOME' -> '110419130002'  (8 digitos espaco-traco 4 digitos)
        - 'C01704361-81-NOME'   -> '0170436181'    (prefixo C/F removido)
        - '33041260 -1358-NOME' -> '330412601358'  (4 digitos de loja)
        """
        if pd.isna(valor):
            return ""
        s = str(valor).strip()
        if not s:
            return ""

        # Usa separador '-' para dividir base e loja (tamanho variavel)
        partes = s.split("-")
        base = re.sub(r"[^a-zA-Z0-9]", "", partes[0])

        # Remove prefixo C/F para matching agnostico (receber/pagar)
        if base and base[0].upper() in ("C", "F"):
            base = base[1:]

        if not base:
            return ""

        loja = ""
        if len(partes) >= 2:
            loja = re.sub(r"\D+", "", partes[1])

        return f"{base}{loja}"

    def _normalizar_codigo_numerico(self, valor: object) -> str:
        """
        Normaliza codigo removendo caracteres especiais e prefixo C/F.

        Garante matching agnostico entre codigos do financeiro (F...) e do razao sem prefixo.
        Ex: 'F110419130002' -> '110419130002'
            'C0170436181'   -> '0170436181'
            '110419130002'  -> '110419130002'
        """
        if pd.isna(valor):
            return ""
        s = str(valor).strip()
        if not s:
            return ""
        clean = re.sub(r"[^a-zA-Z0-9]", "", s)
        # Remove prefixo C/F para matching agnostico
        if clean and clean[0].upper() in ("C", "F"):
            clean = clean[1:]
        return clean

    def _normalizar_item_conta_razao(self, valor: object) -> str:
        """
        Normaliza ITEM CONTA / COD CL VAL do razao geral (CTBR480).

        Suporta:
        - 'C01704361-81-NOME CLIENTE'  -> '0170436181'   (prefixo C removido)
        - 'F11419013-0002-NOME'        -> '110419130002' (prefixo F removido)
        - '11419013 -0002-NOME'        -> '110419130002' (sem prefixo, novo padrao)
        - '33041260 -1358-VIA VAREJO'  -> '330412601358' (4 digitos de loja)
        """
        if pd.isna(valor):
            return ""
        s = str(valor).strip()
        if not s:
            return ""
        partes = s.split("-")
        base = re.sub(r"[^a-zA-Z0-9]", "", partes[0])
        # Remove prefixo C/F para matching agnostico
        if base and base[0].upper() in ("C", "F"):
            base = base[1:]
        loja = ""
        if len(partes) >= 2:
            loja = re.sub(r"\D+", "", partes[1])
        return f"{base}{loja}"

    def _gerar_variacoes_codigo(self, codigo: str) -> List[str]:
        """
        Gera variacoes do codigo para busca flexivel.
        Suporta codigos de tamanho variavel (base e loja).
        Ex: C0170436181 -> ['C0170436181', '0170436181', '170436181']
        """
        variacoes = [codigo]

        # Remove o prefixo C ou F
        if codigo and codigo[0] in ("C", "F"):
            sem_prefixo = codigo[1:]
            variacoes.append(sem_prefixo)

            # Remove zeros a esquerda
            stripped = sem_prefixo.lstrip("0")
            if stripped:
                variacoes.append(stripped)

        return list(set(variacoes))

    def _formatar_data(self, valor: object, periodo: Optional[tuple] = None) -> str:
        """Formata datas em dd/mm/aaaa, tratando serial do Excel e strings MM/DD/AAAA.

        Quando `periodo` (mes, ano) e' informado, datas ambiguas (string onde
        tanto dia quanto mes sao <=12) sao desambiguadas pela leitura
        (MM/DD ou DD/MM) cujo mes/ano resultante bate com o periodo da
        conciliacao -- em vez de assumir sempre o padrao americano.
        """
        if pd.isna(valor):
            return ""

        if isinstance(valor, (datetime, date, pd.Timestamp)):
            try:
                return valor.strftime("%d/%m/%Y")
            except Exception:
                return str(valor)

        if isinstance(valor, (int, float)):
            try:
                dt = pd.to_datetime(valor, unit="D", origin="1899-12-30", errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%d/%m/%Y")
            except Exception:
                pass

        if isinstance(valor, str):
            valor_str = valor.strip()

            # Serial numerico como string (ex: "45306")
            if valor_str and re.fullmatch(r"\d+([.,]\d+)?", valor_str):
                try:
                    numero = float(valor_str.replace(",", "."))
                    dt = pd.to_datetime(numero, unit="D", origin="1899-12-30", errors="coerce")
                    if pd.notna(dt):
                        return dt.strftime("%d/%m/%Y")
                except Exception:
                    pass

            # Se sabemos o periodo da conciliacao, tenta desambiguar pelo mes/ano
            # esperado antes de cair na ordem fixa abaixo -- evita assumir o
            # padrao americano quando a base na verdade esta em DD/MM.
            if periodo is not None:
                mes_esperado, ano_esperado = periodo
                for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
                    try:
                        dt = datetime.strptime(valor_str, fmt)
                    except ValueError:
                        continue
                    if dt.month == mes_esperado and dt.year == ano_esperado:
                        return dt.strftime("%d/%m/%Y")

            # Tenta formatos explicitos em ordem de prioridade.
            # MM/DD/AAAA e tentado antes de DD/MM/AAAA para lidar com datas do razao
            # que chegam no padrao americano (ex: "01/15/2024").
            # Para datas ambiguas (ex: "05/03/2024"), prefere MM/DD por ser o padrao
            # do CTBR480. Se preferir DD/MM em ambiguos, trocar a ordem.
            _FORMATOS = [
                "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO com microssegundos e Z
                "%Y-%m-%dT%H:%M:%SZ",      # ISO com Z
                "%Y-%m-%dT%H:%M:%S",       # ISO sem Z
                "%Y-%m-%d",                # ISO curto
                "%m/%d/%Y",                # MM/DD/AAAA (padrao americano/razao)
                "%d/%m/%Y",                # DD/MM/AAAA (padrao brasileiro)
                "%d-%m-%Y",                # DD-MM-AAAA
                "%m-%d-%Y",                # MM-DD-AAAA
            ]
            for fmt in _FORMATOS:
                try:
                    dt = datetime.strptime(valor_str, fmt)
                    return dt.strftime("%d/%m/%Y")
                except ValueError:
                    continue

        # Ultimo recurso: pandas generico
        try:
            dt = pd.to_datetime(str(valor), errors="coerce")
            if pd.notna(dt):
                return dt.strftime("%d/%m/%Y")
        except Exception:
            pass

        return str(valor)

    def _selecionar_por_diferenca(
        self, lancamentos: List[Dict[str, Any]], diferenca: float, tipo_lancamento: str
    ) -> List[Dict[str, Any]]:
        """Seleciona subconjunto de lancamentos que soma a diferenca (tolerancia 0,01)."""
        alvo = abs(float(diferenca or 0))
        if alvo <= 0.01:
            return []

        candidatos = [
            l for l in lancamentos if l.get("tipo_lancamento") == tipo_lancamento
        ]
        candidatos = sorted(candidatos, key=lambda x: abs(x.get("valor", 0)), reverse=True)

        selecionados: List[Dict[str, Any]] = []
        soma = 0.0
        for item in candidatos:
            valor = float(item.get("valor", 0) or 0)
            if soma + valor - alvo > 0.01:
                continue
            selecionados.append(item)
            soma += valor
            if abs(soma - alvo) <= 0.01:
                break

        return selecionados if abs(soma - alvo) <= 0.01 else []


    def _filtrar_razao_por_codigo(
        self,
        df_razao_norm: pd.DataFrame,
        codigo_normalizado: str,
    ) -> pd.DataFrame:
        """Filtra linhas do razão cujo itemconta_normalizado OR codclval_normalizado bata o código."""
        mask = df_razao_norm["itemconta_normalizado"] == codigo_normalizado
        if "codclval_normalizado" in df_razao_norm.columns:
            mask = mask | (df_razao_norm["codclval_normalizado"] == codigo_normalizado)
        return df_razao_norm[mask]

    def _encontrar_coluna(
        self, df: pd.DataFrame, candidatas: List[str]
    ) -> Optional[str]:
        """Encontra primeira coluna disponivel da lista de candidatas."""
        for col in candidatas:
            if col in df.columns:
                return col
        # Tenta match parcial (case insensitive)
        cols_lower = {c.lower(): c for c in df.columns}
        for cand in candidatas:
            if cand.lower() in cols_lower:
                return cols_lower[cand.lower()]
        return None

    def _classificar_tipo_movimento(
        self,
        conta_origem: str,
        conta_destino: str,
        historico: str,
    ) -> str:
        """Classifica o tipo de movimento contabil baseado nas contas e historico."""
        historico_lower = (historico or "").lower()

        # Padroes de historico para classificacao
        if any(p in historico_lower for p in ["transf", "transfer"]):
            return "TRANSFERENCIA"
        if any(p in historico_lower for p in ["reclassif", "reclassific"]):
            return "RECLASSIFICACAO"
        if any(p in historico_lower for p in ["aloc", "apropri"]):
            return "ALOCACAO"
        if any(p in historico_lower for p in ["auto", "sistem", "integr"]):
            return "LANCAMENTO_AUTOMATICO"

        # Se as contas sao de grupos diferentes, provavelmente e transferencia
        if conta_origem and conta_destino:
            grupo_origem = (
                conta_origem.split(".")[0] if "." in conta_origem else conta_origem[:1]
            )
            grupo_destino = (
                conta_destino.split(".")[0]
                if "." in conta_destino
                else conta_destino[:1]
            )
            if grupo_origem != grupo_destino:
                return "TRANSFERENCIA"

        return "NAO_IDENTIFICADO"

    def _gerar_nota_explicativa(
        self,
        codigo: str,
        valor: float,
        origens: List[Dict[str, Any]],
        status: str,
    ) -> str:
        """Gera nota explicativa clara para exibicao no frontend."""
        if status == "ORIGEM_NAO_IDENTIFICADA":
            return (
                f"Registro {codigo} com valor R$ {valor:,.2f} existe na conta analisada, "
                f"mas nao foi localizado no razao geral. Verificar inconsistencia contabil."
            )

        if len(origens) == 1:
            origem = origens[0]
            tipo = origem.get("tipo_movimento", "NAO_IDENTIFICADO")
            conta = origem.get("conta_origem", "N/A")
            historico = origem.get("historico", "")

            # Incluir historico resumido se disponivel
            hist_resumo = (
                f" ({historico[:50]}...)"
                if len(historico) > 50
                else (f" ({historico})" if historico else "")
            )

            if tipo == "TRANSFERENCIA":
                return f"Contrapartida em {conta}.{hist_resumo}"
            elif tipo == "RECLASSIFICACAO":
                return f"Reclassificacao da conta {conta}.{hist_resumo}"
            elif tipo == "ALOCACAO":
                return f"Apropriacao da conta {conta}.{hist_resumo}"
            elif tipo == "LANCAMENTO_AUTOMATICO":
                return f"Lancamento automatico - contrapartida {conta}.{hist_resumo}"
            else:
                return f"Contrapartida identificada: {conta}.{hist_resumo}"

        # Multiplas origens
        contas = list(set(o.get("conta_origem", "N/A") for o in origens))
        total_valor = sum(o.get("valor", 0) for o in origens)
        return f"Multiplos lancamentos ({len(origens)}) - Contrapartidas: {', '.join(contas[:5])}. Total: R$ {total_valor:,.2f}"

    def analisar_so_contabilidade_profundo(
        self,
        registros_so_contabilidade: List[Dict[str, Any]],
        df_razao_geral: pd.DataFrame,
        conta_analisada: str,
    ) -> List[Dict[str, Any]]:
        """
        Realiza analise profunda dos registros SO_CONTABILIDADE.

        Para cada registro:
        1. Busca no razao geral por correspondencias (codigo, valor, documento)
        2. Identifica conta(s) de origem
        3. Classifica tipo de movimento
        4. Gera nota explicativa para o frontend
        """
        logger.info(
            "[ANALISE PROFUNDA] Iniciando analise de %s registros SO_CONTABILIDADE",
            len(registros_so_contabilidade),
        )
        logger.info(
            "[ANALISE PROFUNDA] Colunas disponiveis no razao geral: %s",
            list(df_razao_geral.columns),
        )
        logger.info(
            "[ANALISE PROFUNDA] Total de linhas no razao geral: %s", len(df_razao_geral)
        )

        if df_razao_geral.empty:
            logger.warning(
                "[ANALISE PROFUNDA] Razao geral vazio - nao e possivel realizar analise"
            )
            return [
                {
                    "codigo": r.get("codigo", ""),
                    "nome": r.get("nome", r.get("codigo", "")),
                    "valor_contabilidade": float(r.get("valor_contabilidade", 0)),
                    "conta_analisada": conta_analisada,
                    "origens_identificadas": [],
                    "total_origens": 0,
                    "status_analise": "ORIGEM_NAO_IDENTIFICADA",
                    "nota_explicativa": "Razao geral nao disponivel para analise.",
                }
                for r in registros_so_contabilidade
            ]

        # Identificar colunas do razao geral
        # Colunas do relatorio: DATA | LOTE/SUB/DOC/LINHA | HISTORICO | XPARTIDA | CCUSTO | ITEMCONTA | CODCLVAL | DEBITO | CREDITO | SALDO ATUAL
        col_codigo = self._encontrar_coluna(
            df_razao_geral,
            [
                "CODCLVAL",
                "codclval",
                "cod_cl_val",
                "COD CL VAL",
                "codigo",
                "Codigo",
                "CODIGO",
                "cod_cliente",
                "cliente_codigo",
                "codigo_cliente",
                "Codigo",
            ],
        )
        col_conta = self._encontrar_coluna(
            df_razao_geral,
            [
                "ITEMCONTA",
                "itemconta",
                "item_conta",
                "ITEM CONTA",
                "conta_contabil",
                "Conta Contabil",
                "conta",
                "Conta",
                "CONTA",
                "conta_contabil_debito",
                "conta_debito",
                "ContaContabil",
            ],
        )
        col_contra_partida = self._encontrar_coluna(
            df_razao_geral,
            [
                "XPARTIDA",
                "xpartida",
                "x_partida",
                "X PARTIDA",
                "contra_partida",
                "contrapartida",
                "conta_credito",
            ],
        )
        col_debito = self._encontrar_coluna(
            df_razao_geral,
            ["DEBITO", "debito", "Debito", "DEBITO", "debito", "vlr_debito"],
        )
        col_credito = self._encontrar_coluna(
            df_razao_geral,
            ["CREDITO", "credito", "Credito", "CREDITO", "credito", "vlr_credito"],
        )
        col_valor = self._encontrar_coluna(
            df_razao_geral,
            [
                "SALDO ATUAL",
                "saldo_atual",
                "SALDO_ATUAL",
                "saldo atual",
                "valor",
                "Valor",
                "VALOR",
                "saldo",
                "Saldo",
            ],
        )
        col_data = self._encontrar_coluna(
            df_razao_geral,
            [
                "DATA",
                "data",
                "Data",
                "data_lancamento",
                "dt_lancamento",
                "data_movimento",
                "dt_movimento",
            ],
        )
        col_documento = self._encontrar_coluna(
            df_razao_geral,
            [
                "LOTE/SUB/DOC/LINHA",
                "lote_sub_doc_linha",
                "LOTE SUB DOC LINHA",
                "documento",
                "Documento",
                "DOCUMENTO",
                "doc",
                "num_documento",
                "nr_documento",
                "numero_documento",
            ],
        )
        col_historico = self._encontrar_coluna(
            df_razao_geral,
            [
                "HISTORICO",
                "historico",
                "Historico",
                "descricao",
                "Descricao",
                "hist_lancamento",
                "observacao",
            ],
        )
        col_centro_custo = self._encontrar_coluna(
            df_razao_geral, ["CCUSTO", "ccusto", "c_custo", "C CUSTO", "centro_custo"]
        )
        col_ct5_desc = self._encontrar_coluna(
            df_razao_geral, ["ct5_desc", "CT5_DESC"]
        )

        logger.info(
            "[ANALISE PROFUNDA] Colunas identificadas - codigo: %s, conta: %s, xpartida: %s, debito: %s, credito: %s",
            col_codigo,
            col_conta,
            col_contra_partida,
            col_debito,
            col_credito,
        )

        # Normalizar codigos no razao geral se a coluna existir
        df_razao = df_razao_geral.copy()
        if col_codigo:
            df_razao["codigo_normalizado"] = df_razao[col_codigo].apply(
                self._normalizar_codigo_razao
            )
            # Tambem guardar o valor original para busca flexivel
            df_razao["codigo_original"] = df_razao[col_codigo].astype(str).str.strip()
        else:
            df_razao["codigo_normalizado"] = ""
            df_razao["codigo_original"] = ""

        if col_conta:
            df_razao["itemconta_normalizado"] = df_razao[col_conta].apply(
                self._normalizar_item_conta_razao
            )
        else:
            df_razao["itemconta_normalizado"] = ""

        # Log de amostra dos codigos no razao para debug
        if col_codigo and not df_razao.empty:
            amostra = (
                df_razao[[col_codigo, "codigo_normalizado"]].head(10).to_dict("records")
            )
            logger.info("[ANALISE PROFUNDA] Amostra de codigos no razao: %s", amostra)

        resultados = []

        for registro in registros_so_contabilidade:
            codigo = str(registro.get("codigo", "")).strip()
            nome = str(registro.get("nome", codigo)).strip()
            valor_cont = float(registro.get("valor_contabilidade", 0))

            logger.info(
                "[ANALISE PROFUNDA] Analisando codigo %s, valor %.2f",
                codigo,
                valor_cont,
            )

            origens = []

            # Normalizar o codigo do registro para matching agnostico (remove prefixo C/F)
            codigo_normalizado = self._normalizar_codigo_numerico(codigo)

            # Buscar TODOS os lancamentos no razao geral para ITEMCONTA = CODIGO
            # Prioridade 1: COD CL VAL (novo formato CTBR480, "codigo_normalizado")
            matches_codigo = pd.DataFrame()
            if col_codigo and "codigo_normalizado" in df_razao.columns:
                matches_codigo = df_razao[
                    df_razao["codigo_normalizado"] == codigo_normalizado
                ]
                logger.info(
                    "[ANALISE PROFUNDA] Registros encontrados por COD CL VAL=%s: %d",
                    codigo_normalizado,
                    len(matches_codigo),
                )

            # Prioridade 2: ITEM CONTA (formato antigo CTBR480, "itemconta_normalizado")
            if matches_codigo.empty and col_conta:
                matches_codigo = df_razao[
                    df_razao["itemconta_normalizado"] == codigo_normalizado
                ]
                logger.info(
                    "[ANALISE PROFUNDA] Registros encontrados por ITEMCONTA=%s: %d",
                    codigo_normalizado,
                    len(matches_codigo),
                )

            # Prioridade 3: Busca flexivel por variacoes no campo de codigo original
            if matches_codigo.empty and col_codigo:
                variacoes = self._gerar_variacoes_codigo(codigo)
                logger.info(
                    "[ANALISE PROFUNDA] Variacoes do codigo %s: %s", codigo, variacoes
                )

                for var in variacoes:
                    matches_codigo = df_razao[df_razao["codigo_original"] == var]
                    if not matches_codigo.empty:
                        logger.info(
                            "[ANALISE PROFUNDA] Match encontrado com variacao '%s'",
                            var,
                        )
                        break

                logger.info(
                    "[ANALISE PROFUNDA] Registros encontrados para %s: %d",
                    codigo,
                    len(matches_codigo),
                )

            # Listar TODOS os lancamentos encontrados (nao filtrar por XPARTIDA)
            if not matches_codigo.empty:
                for _, row in matches_codigo.iterrows():
                    # Conta do lancamento (ITEMCONTA ou similar)
                    item_conta = str(row.get(col_conta, "")) if col_conta else ""
                    # Contrapartida (se existir)
                    contra_partida = (
                        str(row.get(col_contra_partida, ""))
                        if col_contra_partida
                        else ""
                    )

                    # Calcular valor: DEBITO ou CREDITO (o que tiver valor)
                    valor_debito = 0.0
                    valor_credito = 0.0
                    if col_debito:
                        try:
                            val = row.get(col_debito, 0)
                            if pd.notna(val):
                                valor_debito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_debito = 0.0
                    if col_credito:
                        try:
                            val = row.get(col_credito, 0)
                            if pd.notna(val):
                                valor_credito = self._parse_valor(val)
                        except (ValueError, TypeError):
                            valor_credito = 0.0

                    # Valor e debito ou credito (o que tiver)
                    valor_lancamento = (
                        valor_debito if valor_debito > 0 else valor_credito
                    )
                    tipo_lancamento = (
                        "D"
                        if valor_debito > 0
                        else ("C" if valor_credito > 0 else "")
                    )

                    data_lancamento = (
                        self._formatar_data(row.get(col_data, "")) if col_data else ""
                    )
                    documento = str(row.get(col_documento, "")) if col_documento else ""
                    historico = str(row.get(col_historico, "")) if col_historico else ""

                    # Determinar tipo de movimento baseado no historico
                    tipo_movimento = self._classificar_tipo_movimento(
                        contra_partida, conta_analisada, historico
                    )

                    # Usar contrapartida como conta_origem, ou a propria conta se nao tiver
                    conta_para_exibir = (
                        contra_partida
                        if contra_partida and contra_partida not in ["", "nan", "None"]
                        else item_conta
                    )

                    origens.append(
                        {
                            "conta_origem": conta_para_exibir,
                            "descricao_conta": nome if nome and nome != codigo else "",
                            "valor": round(valor_lancamento, 2),
                            "tipo_lancamento": tipo_lancamento,
                            "data_lancamento": data_lancamento,
                            "documento": documento,
                            "historico": historico,
                            "tipo_movimento": tipo_movimento,
                            "ct5_desc": str(row.get(col_ct5_desc, "")) if col_ct5_desc else "",
                        }
                    )

            # Determinar status da analise
            if len(origens) == 0:
                status_analise = "ORIGEM_NAO_IDENTIFICADA"
            elif len(origens) == 1:
                status_analise = "ORIGEM_IDENTIFICADA"
            else:
                status_analise = "MULTIPLAS_ORIGENS"

            nota = self._gerar_nota_explicativa(
                codigo, valor_cont, origens, status_analise
            )

            resultados.append(
                {
                    "codigo": codigo,
                    "nome": nome,
                    "valor_contabilidade": round(valor_cont, 2),
                    "conta_analisada": conta_analisada,
                    "origens_identificadas": origens,
                    "total_origens": len(origens),
                    "status_analise": status_analise,
                    "nota_explicativa": nota,
                }
            )

        # Estatisticas
        total = len(resultados)
        identificados = sum(
            1 for r in resultados if r["status_analise"] != "ORIGEM_NAO_IDENTIFICADA"
        )
        logger.info(
            "[ANALISE PROFUNDA] Concluida: %s registros, %s com origem identificada (%.1f%%)",
            total,
            identificados,
            (identificados / total * 100) if total else 0,
        )

        return resultados
