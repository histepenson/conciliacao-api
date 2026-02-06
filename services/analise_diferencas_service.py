from typing import List, Dict, Any, Optional
from datetime import datetime, date
import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)


class AnaliseDiferencasService:
    """Gera análise detalhada por código (financeiro/contábil)."""

    def _classificar_tipo(
        self, valor_fin: float, valor_cont: float, diferenca: float
    ) -> str:
        if abs(diferenca) <= 0.01:
            return "CONCILIADO"
        if valor_fin > 0 and valor_cont == 0:
            return "SO_FINANCEIRO"
        if valor_cont > 0 and valor_fin == 0:
            return "SO_CONTABILIDADE"
        return "DIVERGENTE_VALOR"

    def _status(self, diferenca: float) -> str:
        return "verde" if abs(diferenca) <= 0.01 else "vermelho"

    def processar_analise_detalhada(
        self,
        df_financeiro: pd.DataFrame,
        df_contabilidade_filtrada: pd.DataFrame,
        df_razao_contabil: pd.DataFrame,
        conta_contabil: str,
        df_financeiro_detalhado: Optional[pd.DataFrame] = None,
        df_razao_geral: Optional[pd.DataFrame] = None,
    ) -> List[Dict[str, Any]]:
        """
        Consolida valores por código e gera uma análise detalhada financeira.
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

        # Criar mapa de código -> nome do cliente para uso em todos os lançamentos
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
        if df_razao_geral is not None and not df_razao_geral.empty:
            col_itemconta_geral = self._encontrar_coluna(
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
            if col_itemconta_geral:
                df_razao_geral_norm = df_razao_geral.copy()
                df_razao_geral_norm["itemconta_normalizado"] = df_razao_geral_norm[col_itemconta_geral].apply(
                    self._normalizar_codigo_numerico
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

        df_merge = fin_agg.merge(cont_agg, on="codigo", how="outer")
        if not razao_agg.empty:
            df_merge = df_merge.merge(razao_agg, on="codigo", how="left")
        else:
            df_merge["lancamentos_razao"] = 0

        df_merge["valor_financeiro"] = df_merge["valor_financeiro"].fillna(0.0)
        df_merge["valor_contabilidade"] = df_merge["valor_contabilidade"].fillna(0.0)
        df_merge["lancamentos_razao"] = (
            df_merge["lancamentos_razao"].fillna(0).astype(int)
        )

        df_merge["nome"] = df_merge["nome_fin"].fillna(df_merge["nome_cont"])
        df_merge["diferenca"] = (
            df_merge["valor_contabilidade"] - df_merge["valor_financeiro"]
        )

        financeiro_match_map: Dict[tuple[str, str], List[float]] = {}
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
                    key = (row_fin.get("codigo", ""), row_fin.get("data_match", ""))
                    financeiro_match_map.setdefault(key, []).append(
                        float(row_fin.get("valor_match", 0.0))
                    )

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

        analises: List[Dict[str, Any]] = []
        for row in df_merge.to_dict("records"):
            codigo = str(row.get("codigo", "")).strip()
            valor_fin = float(row.get("valor_financeiro", 0.0))
            valor_cont = float(row.get("valor_contabilidade", 0.0))
            diferenca = float(row.get("diferenca", 0.0))
            tipo = self._classificar_tipo(valor_fin, valor_cont, diferenca)
            status = self._status(diferenca)

            # A coluna exibida como "Fornecedor" no frontend deve mostrar o código.
            nome_exibicao = codigo or str(row.get("nome") or "").strip()

            lancamentos_razao = int(row.get("lancamentos_razao", 0))
            lancamentos_razao_detalhes: List[Dict[str, Any]] = []
            lancamentos_financeiro_detalhes: List[Dict[str, Any]] = []
            lancamentos_razao_sem_financeiro: List[Dict[str, Any]] = []
            registros_match_financeiro: List[Dict[str, Any]] = []
            registros_match_contabilidade: List[Dict[str, Any]] = []
            sem_lancamentos_razao = False
            nota_razao = ""

            matches_razao_count = 0
            if df_razao_geral_norm is not None and col_itemconta_geral:
                codigo_normalizado = self._normalizar_codigo_numerico(codigo)
                matches_razao_count = int(
                    (df_razao_geral_norm["itemconta_normalizado"] == codigo_normalizado).sum()
                )
                if (
                    matches_razao_count == 0
                    and abs(diferenca) > 0.01
                    and tipo == "SO_CONTABILIDADE"
                ):
                    sem_lancamentos_razao = True
                    nota_razao = "Sem lançamentos no período."
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
                                    valor_debito = float(
                                        str(val).replace(".", "").replace(",", ".")
                                        or 0
                                    )
                            except (ValueError, TypeError):
                                valor_debito = 0.0
                        if col_credito_geral:
                            try:
                                val = r.get(col_credito_geral, 0)
                                if pd.notna(val):
                                    valor_credito = float(
                                        str(val).replace(".", "").replace(",", ".")
                                        or 0
                                    )
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
                            r.get(col_data_geral, "") if col_data_geral else ""
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
                                "data_lancamento": data_lanc,
                                "documento": str(r.get(col_documento_geral, ""))
                                if col_documento_geral
                                else "",
                                "historico": str(r.get(col_historico_geral, ""))
                                if col_historico_geral
                                else "",
                                "tipo_movimento": "NAO_IDENTIFICADO",
                            }
                        )

                lancamentos_razao = int(
                    lancamentos_razao_geral.get(codigo_normalizado, 0)
                )

                # Em SO_CONTABILIDADE, listar apenas o que explica a diferenca
                lancamentos_razao_detalhes = self._selecionar_por_diferenca(
                    lancamentos_razao_detalhes, diferenca, "D"
                )

            if (
                valor_cont > valor_fin
                and df_razao_geral_norm is not None
                and col_itemconta_geral
            ):
                codigo_normalizado = self._normalizar_codigo_numerico(codigo)
                matches_item = df_razao_geral_norm[
                    df_razao_geral_norm["itemconta_normalizado"] == codigo_normalizado
                ]
                for _, r in matches_item.iterrows():
                    valor_debito = 0.0
                    valor_credito = 0.0
                    if col_debito_geral:
                        try:
                            val = r.get(col_debito_geral, 0)
                            if pd.notna(val):
                                valor_debito = float(
                                    str(val).replace(".", "").replace(",", ".") or 0
                                )
                        except (ValueError, TypeError):
                            valor_debito = 0.0
                    if col_credito_geral:
                        try:
                            val = r.get(col_credito_geral, 0)
                            if pd.notna(val):
                                valor_credito = float(
                                    str(val).replace(".", "").replace(",", ".") or 0
                                )
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
                        r.get(col_data_geral, "") if col_data_geral else ""
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
                            "data_lancamento": data_lanc,
                            "documento": str(r.get(col_documento_geral, ""))
                            if col_documento_geral
                            else "",
                            "historico": str(r.get(col_historico_geral, ""))
                            if col_historico_geral
                            else "",
                            "tipo_movimento": "NAO_IDENTIFICADO",
                        }
                    )

                # Em divergencia contabilidade > financeiro, listar apenas o que explica a diferenca
                lancamentos_razao_sem_financeiro = self._selecionar_por_diferenca(
                    lancamentos_razao_sem_financeiro, diferenca, "D"
                )

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
                    prf_numero = r.get("prf_numero", "")
                    parcela = r.get("parcela", "")

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

                    lancamentos_financeiro_detalhes.append(
                        {
                            "conta_origem": codigo,
                            "descricao_conta": cliente,
                            "valor": round(valor_fin_det, 2),
                            "tipo_lancamento": "",
                            "data_lancamento": self._formatar_data(data_emissao),
                            "documento": documento,
                            "historico": "",
                            "tipo_movimento": "NAO_IDENTIFICADO",
                        }
                    )

            if (
                valor_cont < valor_fin
                and df_razao_geral_norm is not None
                and col_itemconta_geral
            ):
                codigo_normalizado = self._normalizar_codigo_numerico(codigo)
                matches_item = df_razao_geral_norm[
                    df_razao_geral_norm["itemconta_normalizado"] == codigo_normalizado
                ]
                lancamentos_credito: List[Dict[str, Any]] = []
                for _, r in matches_item.iterrows():
                    valor_debito = 0.0
                    valor_credito = 0.0
                    if col_debito_geral:
                        try:
                            val = r.get(col_debito_geral, 0)
                            if pd.notna(val):
                                valor_debito = float(
                                    str(val).replace(".", "").replace(",", ".") or 0
                                )
                        except (ValueError, TypeError):
                            valor_debito = 0.0
                    if col_credito_geral:
                        try:
                            val = r.get(col_credito_geral, 0)
                            if pd.notna(val):
                                valor_credito = float(
                                    str(val).replace(".", "").replace(",", ".") or 0
                                )
                        except (ValueError, TypeError):
                            valor_credito = 0.0

                    if abs(valor_credito) <= 0:
                        continue

                    data_lanc = self._formatar_data(
                        r.get(col_data_geral, "") if col_data_geral else ""
                    )
                    if _tem_match_financeiro(codigo, data_lanc, abs(valor_credito)):
                        continue

                    item_conta = (
                        str(r.get(col_itemconta_geral, ""))
                        if col_itemconta_geral
                        else ""
                    )
                    # Obter nome do cliente do mapa
                    nome_cliente = codigo_nome_map.get(codigo, "")

                    lancamentos_credito.append(
                        {
                            "conta_origem": item_conta,
                            "descricao_conta": nome_cliente if nome_cliente else "",
                            "valor": round(abs(valor_credito), 2),
                            "tipo_lancamento": "C",
                            "data_lancamento": data_lanc,
                            "documento": str(r.get(col_documento_geral, ""))
                            if col_documento_geral
                            else "",
                            "historico": str(r.get(col_historico_geral, ""))
                            if col_historico_geral
                            else "",
                            "tipo_movimento": "NAO_IDENTIFICADO",
                        }
                    )

                lancamentos_razao_sem_financeiro = self._selecionar_por_diferenca(
                    lancamentos_credito, diferenca, "C"
                )

            # Registros individuais de ambas as bases (para todos os tipos)
            status_registro = "conciliado" if tipo == "CONCILIADO" else "divergente"

            # Financeiro detalhado
            if df_financeiro_detalhado is not None and not df_financeiro_detalhado.empty:
                if "codigo" in df_financeiro_detalhado.columns:
                    matches_fin_det = df_financeiro_detalhado[
                        df_financeiro_detalhado["codigo"].astype(str).str.strip() == codigo
                    ]
                    for _, r in matches_fin_det.iterrows():
                        prf = r.get("prf_numero", "")
                        parcela_val = r.get("parcela", "")
                        doc_parts = []
                        if prf not in [None, ""] and not pd.isna(prf):
                            doc_parts.append(str(prf).strip())
                        if parcela_val not in [None, ""] and not pd.isna(parcela_val):
                            p_str = str(parcela_val).strip()
                            if p_str and p_str not in doc_parts:
                                doc_parts.append(p_str)
                        registros_match_financeiro.append({
                            "descricao": str(r.get("cliente", "")).strip(),
                            "valor": round(float(r.get("valor", 0) or 0), 2),
                            "data_emissao": self._formatar_data(r.get("data_emissao", "")),
                            "documento": "-".join(doc_parts),
                            "status": status_registro,
                        })

            # Contabilidade
            matches_cont_det = df_cont[df_cont["codigo"].astype(str).str.strip() == codigo]
            for _, r in matches_cont_det.iterrows():
                registros_match_contabilidade.append({
                    "descricao": str(r.get("cliente", "")).strip(),
                    "valor": round(float(r.get("valor", 0) or 0), 2),
                    "status": status_registro,
                })

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
                    "lancamentos_razao": lancamentos_razao,
                    "lancamentos_razao_detalhes": lancamentos_razao_detalhes
                    if lancamentos_razao_detalhes
                    else lancamentos_razao_sem_financeiro,
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
    # ANÁLISE PROFUNDA SO_CONTABILIDADE
    # ==================================================

    def _normalizar_codigo_razao(self, valor: object) -> str:
        """Normaliza código do razão geral para formato C{base}{loja}."""
        if pd.isna(valor):
            return ""
        s = str(valor).strip()
        if not s:
            return ""

        # Usa separador '-' para dividir base e loja (tamanho variável)
        # Sem separador: todos os caracteres formam o código completo
        partes = s.split("-")
        base = re.sub(r"[^a-zA-Z0-9]", "", partes[0])

        if not base:
            return ""

        loja = ""
        if len(partes) >= 2:
            loja = re.sub(r"\D+", "", partes[1])

        return f"C{base}{loja}"

    def _normalizar_codigo_numerico(self, valor: object) -> str:
        """Normaliza código preservando prefixo C/F e letras, removendo apenas caracteres especiais."""
        if pd.isna(valor):
            return ""
        s = str(valor).strip()
        if not s:
            return ""
        # Mantém letras + dígitos (incluindo prefixo C/F que faz parte do código)
        clean = re.sub(r"[^a-zA-Z0-9]", "", s)
        return clean

    def _gerar_variacoes_codigo(self, codigo: str) -> List[str]:
        """
        Gera variações do código para busca flexível.
        Suporta códigos de tamanho variável (base e loja).
        Ex: C0170436181 -> ['C0170436181', '0170436181', '170436181']
        """
        variacoes = [codigo]

        # Remove o prefixo C ou F
        if codigo and codigo[0] in ("C", "F"):
            sem_prefixo = codigo[1:]
            variacoes.append(sem_prefixo)

            # Remove zeros à esquerda
            stripped = sem_prefixo.lstrip("0")
            if stripped:
                variacoes.append(stripped)

        return list(set(variacoes))

    def _formatar_data(self, valor: object) -> str:
        """Formata datas em dd/mm/aaaa, tratando serial do Excel."""
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
            if valor_str and re.fullmatch(r"\d+([.,]\d+)?", valor_str):
                try:
                    numero = float(valor_str.replace(",", "."))
                    dt = pd.to_datetime(numero, unit="D", origin="1899-12-30", errors="coerce")
                    if pd.notna(dt):
                        return dt.strftime("%d/%m/%Y")
                except Exception:
                    pass

        try:
            dt = pd.to_datetime(str(valor), dayfirst=True, errors="coerce")
            if pd.notna(dt):
                return dt.strftime("%d/%m/%Y")
        except Exception:
            pass

        return str(valor)

    def _selecionar_por_diferenca(
        self, lancamentos: List[Dict[str, Any]], diferenca: float, tipo_lancamento: str
    ) -> List[Dict[str, Any]]:
        """Seleciona subconjunto de lançamentos que soma a diferença (tolerância 0,01)."""
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


    def _encontrar_coluna(
        self, df: pd.DataFrame, candidatas: List[str]
    ) -> Optional[str]:
        """Encontra primeira coluna disponível da lista de candidatas."""
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
        """Classifica o tipo de movimento contábil baseado nas contas e histórico."""
        historico_lower = (historico or "").lower()

        # Padrões de histórico para classificação
        if any(p in historico_lower for p in ["transf", "transfer"]):
            return "TRANSFERENCIA"
        if any(p in historico_lower for p in ["reclassif", "reclassific"]):
            return "RECLASSIFICACAO"
        if any(p in historico_lower for p in ["aloc", "apropri"]):
            return "ALOCACAO"
        if any(p in historico_lower for p in ["auto", "sistem", "integr"]):
            return "LANCAMENTO_AUTOMATICO"

        # Se as contas são de grupos diferentes, provavelmente é transferência
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
        """Gera nota explicativa clara para exibição no frontend."""
        if status == "ORIGEM_NAO_IDENTIFICADA":
            return (
                f"Registro {codigo} com valor R$ {valor:,.2f} existe na conta analisada, "
                f"mas não foi localizado no razão geral. Verificar inconsistência contábil."
            )

        if len(origens) == 1:
            origem = origens[0]
            tipo = origem.get("tipo_movimento", "NAO_IDENTIFICADO")
            conta = origem.get("conta_origem", "N/A")
            historico = origem.get("historico", "")

            # Incluir histórico resumido se disponível
            hist_resumo = (
                f" ({historico[:50]}...)"
                if len(historico) > 50
                else (f" ({historico})" if historico else "")
            )

            if tipo == "TRANSFERENCIA":
                return f"Contrapartida em {conta}.{hist_resumo}"
            elif tipo == "RECLASSIFICACAO":
                return f"Reclassificação da conta {conta}.{hist_resumo}"
            elif tipo == "ALOCACAO":
                return f"Apropriação da conta {conta}.{hist_resumo}"
            elif tipo == "LANCAMENTO_AUTOMATICO":
                return f"Lançamento automático - contrapartida {conta}.{hist_resumo}"
            else:
                return f"Contrapartida identificada: {conta}.{hist_resumo}"

        # Múltiplas origens
        contas = list(set(o.get("conta_origem", "N/A") for o in origens))
        total_valor = sum(o.get("valor", 0) for o in origens)
        return f"Múltiplos lançamentos ({len(origens)}) - Contrapartidas: {', '.join(contas[:5])}. Total: R$ {total_valor:,.2f}"

    def analisar_so_contabilidade_profundo(
        self,
        registros_so_contabilidade: List[Dict[str, Any]],
        df_razao_geral: pd.DataFrame,
        conta_analisada: str,
    ) -> List[Dict[str, Any]]:
        """
        Realiza análise profunda dos registros SO_CONTABILIDADE.

        Para cada registro:
        1. Busca no razão geral por correspondências (código, valor, documento)
        2. Identifica conta(s) de origem
        3. Classifica tipo de movimento
        4. Gera nota explicativa para o frontend
        """
        logger.info(
            "[ANÁLISE PROFUNDA] Iniciando análise de %s registros SO_CONTABILIDADE",
            len(registros_so_contabilidade),
        )
        logger.info(
            "[ANÁLISE PROFUNDA] Colunas disponíveis no razão geral: %s",
            list(df_razao_geral.columns),
        )
        logger.info(
            "[ANÁLISE PROFUNDA] Total de linhas no razão geral: %s", len(df_razao_geral)
        )

        if df_razao_geral.empty:
            logger.warning(
                "[ANÁLISE PROFUNDA] Razão geral vazio - não é possível realizar análise"
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
                    "nota_explicativa": "Razão geral não disponível para análise.",
                }
                for r in registros_so_contabilidade
            ]

        # Identificar colunas do razão geral
        # Colunas do relatório: DATA | LOTE/SUB/DOC/LINHA | HISTORICO | XPARTIDA | CCUSTO | ITEMCONTA | CODCLVAL | DEBITO | CREDITO | SALDO ATUAL
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
                "Código",
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
                "Conta Contábil",
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
            ["DEBITO", "debito", "Debito", "DÉBITO", "débito", "vlr_debito"],
        )
        col_credito = self._encontrar_coluna(
            df_razao_geral,
            ["CREDITO", "credito", "Credito", "CRÉDITO", "crédito", "vlr_credito"],
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

        logger.info(
            "[ANÁLISE PROFUNDA] Colunas identificadas - codigo: %s, conta: %s, xpartida: %s, debito: %s, credito: %s",
            col_codigo,
            col_conta,
            col_contra_partida,
            col_debito,
            col_credito,
        )

        # Normalizar códigos no razão geral se a coluna existir
        df_razao = df_razao_geral.copy()
        if col_codigo:
            df_razao["codigo_normalizado"] = df_razao[col_codigo].apply(
                self._normalizar_codigo_razao
            )
            # Também guardar o valor original para busca flexível
            df_razao["codigo_original"] = df_razao[col_codigo].astype(str).str.strip()
        else:
            df_razao["codigo_normalizado"] = ""
            df_razao["codigo_original"] = ""

        if col_conta:
            df_razao["itemconta_normalizado"] = df_razao[col_conta].apply(
                self._normalizar_codigo_numerico
            )
        else:
            df_razao["itemconta_normalizado"] = ""

        # Log de amostra dos códigos no razão para debug
        if col_codigo and not df_razao.empty:
            amostra = (
                df_razao[[col_codigo, "codigo_normalizado"]].head(10).to_dict("records")
            )
            logger.info("[ANÁLISE PROFUNDA] Amostra de códigos no razão: %s", amostra)

        resultados = []

        for registro in registros_so_contabilidade:
            codigo = str(registro.get("codigo", "")).strip()
            nome = str(registro.get("nome", codigo)).strip()
            valor_cont = float(registro.get("valor_contabilidade", 0))

            logger.info(
                "[ANÁLISE PROFUNDA] Analisando código %s, valor %.2f",
                codigo,
                valor_cont,
            )

            origens = []

            # Buscar TODOS os lançamentos no razão geral para ITEMCONTA = CODIGO
            matches_codigo = pd.DataFrame()
            if col_conta:
                codigo_normalizado = self._normalizar_codigo_numerico(codigo)
                matches_codigo = df_razao[
                    df_razao["itemconta_normalizado"] == codigo_normalizado
                ]
                logger.info(
                    "[ANÁLISE PROFUNDA] Registros encontrados por ITEMCONTA=%s: %d",
                    codigo_normalizado,
                    len(matches_codigo),
                )

            # Se não há coluna ITEMCONTA, manter fallback para o campo de código
            if matches_codigo.empty and col_codigo:
                # Gerar variações do código para busca flexível
                variacoes = self._gerar_variacoes_codigo(codigo)
                logger.info(
                    "[ANÁLISE PROFUNDA] Variações do código %s: %s", codigo, variacoes
                )

                # Primeiro tenta match exato pelo código normalizado
                matches_codigo = df_razao[df_razao["codigo_normalizado"] == codigo]

                # Se não encontrou, tenta pelas variações no código original
                if matches_codigo.empty:
                    for var in variacoes:
                        matches_codigo = df_razao[df_razao["codigo_original"] == var]
                        if not matches_codigo.empty:
                            logger.info(
                                "[ANÁLISE PROFUNDA] Match encontrado com variação '%s'",
                                var,
                            )
                            break

                logger.info(
                    "[ANÁLISE PROFUNDA] Registros encontrados para %s: %d",
                    codigo,
                    len(matches_codigo),
                )

            # Listar TODOS os lançamentos encontrados (não filtrar por XPARTIDA)
            if not matches_codigo.empty:
                for _, row in matches_codigo.iterrows():
                    # Conta do lançamento (ITEMCONTA ou similar)
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
                                valor_debito = float(
                                    str(val).replace(".", "").replace(",", ".") or 0
                                )
                        except (ValueError, TypeError):
                            valor_debito = 0.0
                    if col_credito:
                        try:
                            val = row.get(col_credito, 0)
                            if pd.notna(val):
                                valor_credito = float(
                                    str(val).replace(".", "").replace(",", ".") or 0
                                )
                        except (ValueError, TypeError):
                            valor_credito = 0.0

                    # Valor é débito ou crédito (o que tiver)
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

                    # Determinar tipo de movimento baseado no histórico
                    tipo_movimento = self._classificar_tipo_movimento(
                        contra_partida, conta_analisada, historico
                    )

                    # Usar contrapartida como conta_origem, ou a própria conta se não tiver
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
                        }
                    )

            # Determinar status da análise
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

        # Estatísticas
        total = len(resultados)
        identificados = sum(
            1 for r in resultados if r["status_analise"] != "ORIGEM_NAO_IDENTIFICADA"
        )
        logger.info(
            "[ANÁLISE PROFUNDA] Concluída: %s registros, %s com origem identificada (%.1f%%)",
            total,
            identificados,
            (identificados / total * 100) if total else 0,
        )

        return resultados
