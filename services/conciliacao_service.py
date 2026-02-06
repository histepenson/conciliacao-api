import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from schemas.conciliacao_schema import RequestConciliacao
from services.analise_diferencas_service import AnaliseDiferencasService
from tools.calc_diferencas import calcular_diferencas
from tools.contabilidade import normalizar_planilha_contabilidade
from tools.financeiro import (
    normalizar_planilha_financeira,
    normalizar_planilha_financeira_detalhada,
)
from tools.financeiro.factory import (
    get_processador_por_nome,
    TipoFinanceiro,
    validar_layout_planilha,
)
from tools.mappers import map_origem_maior

logger = logging.getLogger(__name__)


class ConciliacaoService:

    # ==================================================
    # VALIDAÇÃO
    # ==================================================
    def validar_dados(self, request: RequestConciliacao) -> tuple[bool, str]:
        if not request.base_origem or not request.base_origem.registros:
            return False, "Base de origem vazia"

        if not request.base_contabil_filtrada or not request.base_contabil_filtrada.registros:
            return False, "Base contábil filtrada vazia"

        if not request.base_contabil_geral or not request.base_contabil_geral.registros:
            return False, "Base geral da contabilidade vazia"

        if not request.parametros or not request.parametros.get("data_base"):
            return False, "Data-base não informada"

        return True, ""

    def _filtrar_razao_por_conta(self, df_razao: pd.DataFrame, conta_contabil: str) -> pd.DataFrame:
        """Filtra o razão pela conta contábil sendo conciliada, se a coluna existir."""
        if df_razao.empty:
            return df_razao

        colunas_candidatas = ["conta_contabil", "Conta Contábil", "conta"]
        coluna_conta: Optional[str] = next((c for c in colunas_candidatas if c in df_razao.columns), None)

        if not coluna_conta:
            logger.info("[ANÁLISE DETALHADA] Coluna de conta não encontrada no razão; usando razão completo")
            return df_razao

        df_filtrado = df_razao[df_razao[coluna_conta].astype(str) == str(conta_contabil)].copy()
        logger.info(
            "[ANÁLISE DETALHADA] Razão filtrado por conta %s: %s -> %s registros",
            conta_contabil,
            len(df_razao),
            len(df_filtrado),
        )
        return df_filtrado

    def _formatar_resumo_analise(self, total: int, conciliados: int) -> dict:
        divergentes = int(total - conciliados)
        percentual = (conciliados / total * 100) if total else 0.0
        return {
            "total_registros": int(total),
            "total": int(total),
            "conciliados": int(conciliados),
            "divergentes": int(divergentes),
            "percentual_conciliacao": round(percentual, 2),
            "percentual": round(percentual, 2),
        }

    def _gerar_resumo_analise_fallback(self, df_completo: pd.DataFrame) -> dict:
        """Gera resumo da análise diretamente do df_completo, sem depender da análise detalhada."""
        if df_completo is None or df_completo.empty:
            return self._formatar_resumo_analise(total=0, conciliados=0)

        dif_abs = pd.to_numeric(df_completo.get("Diferença Absoluta"), errors="coerce").fillna(0.0)
        conciliados = int((dif_abs <= 0.01).sum())
        total = int(len(df_completo))
        resumo = self._formatar_resumo_analise(total=total, conciliados=conciliados)
        logger.info("[ANÁLISE DETALHADA] Resumo fallback: %s", resumo)
        return resumo

    # ==================================================
    # EXECUÇÃO PRINCIPAL
    # ==================================================
    def executar(self, request: RequestConciliacao) -> dict:
        """
        Retorna dict para compatibilidade com o frontend.
        """
        logger.info("⚙️ Executando conciliação contábil")

        # ==========================
        # 1️⃣ NORMALIZAR FINANCEIRO
        # ==========================
        df_financeiro_raw = pd.DataFrame(request.base_origem.registros)
        logger.info("📊 Registros origem recebidos: %s", len(df_financeiro_raw))

        # Detectar tipo financeiro (contas_receber ou contas_pagar)
        tipo_financeiro = request.parametros.get("tipo_financeiro", "contas_receber")
        # Também verificar no base_origem.tipo para retrocompatibilidade
        if hasattr(request.base_origem, "tipo") and request.base_origem.tipo:
            tipo_financeiro = request.base_origem.tipo
        logger.info("📋 Tipo financeiro: %s", tipo_financeiro)

        # Validar layout do arquivo financeiro ANTES de processar
        validacao_layout = validar_layout_planilha(df_financeiro_raw, tipo_financeiro)
        if not validacao_layout.valido:
            logger.error("❌ Layout inválido: %s", validacao_layout.mensagem)
            raise ValueError(
                f"Layout do arquivo financeiro inválido: {validacao_layout.mensagem} "
                f"Colunas encontradas no arquivo: {validacao_layout.colunas_arquivo}"
            )

        if validacao_layout.avisos:
            for aviso in validacao_layout.avisos:
                logger.warning("⚠️ %s", aviso)

        # Usar o processador apropriado via factory
        try:
            processador = get_processador_por_nome(tipo_financeiro)
            financeiro_norm = processador.normalizar(df_financeiro_raw)
            financeiro_detalhado = processador.normalizar_detalhado(df_financeiro_raw)
            logger.info("✅ %s normalizado via factory: %s registros", tipo_financeiro.upper(), len(financeiro_norm))
        except ValueError as e:
            # Se for erro de layout, propagar com mensagem clara
            if "coluna" in str(e).lower() or "encontrada" in str(e).lower():
                raise ValueError(f"Erro no layout do arquivo financeiro: {str(e)}")
            # Fallback para o método legado (contas a receber) se tipo não reconhecido
            logger.warning("⚠️ Tipo '%s' não reconhecido, usando processador padrão (contas_receber)", tipo_financeiro)
            financeiro_norm = normalizar_planilha_financeira(df_financeiro_raw)
            financeiro_detalhado = normalizar_planilha_financeira_detalhada(df_financeiro_raw)
            logger.info("✅ Financeiro normalizado (legado): %s registros", len(financeiro_norm))

        # ==========================
        # 2️⃣ NORMALIZAR CONTABILIDADE
        # ==========================
        df_contabil_raw = pd.DataFrame(request.base_contabil_filtrada.registros)
        logger.info("📊 Registros contábeis recebidos: %s", len(df_contabil_raw))

        contabil_norm = normalizar_planilha_contabilidade(df_contabil_raw)
        logger.info("✅ Contabilidade normalizada: %s registros", len(contabil_norm))

        # ==========================
        # 3️⃣ CALCULAR DIFERENÇAS
        # ==========================
        resultado = calcular_diferencas(
            df_financeiro=financeiro_norm,
            df_contabilidade=contabil_norm,
            salvar_arquivo=False,
        )

        resumo_calc = resultado["resumo"]
        df_completo = resultado["df_completo"]

        logger.info("📈 Resumo calculado: %s", resumo_calc)
        logger.info("🔍 Colunas do df_completo: %s", df_completo.columns.tolist())

        # ==========================
        # 4️⃣ FILTRAR DIFERENÇAS
        # ==========================
        df_origem_maior = df_completo[
            df_completo["Tipo Diferença"] == "Financeiro > Contabilidade"
        ].copy()

        df_contabil_maior = df_completo[
            df_completo["Tipo Diferença"] == "Contabilidade > Financeiro"
        ].copy()

        logger.info("📊 Diferenças Origem > Contábil: %s", len(df_origem_maior))
        logger.info("📊 Diferenças Contábil > Origem: %s", len(df_contabil_maior))

        # ==========================
        # 5️⃣ MAPEAR DIFERENÇAS (SCHEMA)
        # ==========================
        diferencas_origem_maior = []
        for row_dict in df_origem_maior.to_dict("records"):
            try:
                mapped = map_origem_maior(row_dict)
                diferencas_origem_maior.append(mapped)
            except Exception as exc:
                logger.error("❌ Erro ao mapear origem_maior: %s", exc)
                logger.error("   Row problemático: %s", row_dict)

        diferencas_contabilidade_maior = []
        conta_contabil = request.base_contabil_filtrada.conta_contabil
        for row_dict in df_contabil_maior.to_dict("records"):
            try:
                diferencas_contabilidade_maior.append(
                    {
                        "identificador": str(row_dict.get("Código", "")).strip(),
                        "data": None,
                        "valor": float(row_dict.get("Diferença", 0) or 0),
                        "conta_contabil": conta_contabil,
                        "historico": "Valor maior na Contabilidade",
                        "existe_origem": False,
                        "verificacoes_realizadas": ["Comparação por código"],
                        "situacao": "DIVERGENTE",
                    }
                )
            except Exception as exc:
                logger.error("❌ Erro ao mapear contabil_maior: %s", exc)
                logger.error("   Row problemático: %s", row_dict)

        logger.info(
            "✅ Mapeados: %s origem_maior, %s contabil_maior",
            len(diferencas_origem_maior),
            len(diferencas_contabilidade_maior),
        )

        # ==========================
        # 6️⃣ RESUMO (FORMATO FRONTEND)
        # ==========================
        total_origem = float(resumo_calc.get("valor_total_financeiro", 0) or 0)
        total_destino = float(resumo_calc.get("valor_total_contabilidade", 0) or 0)
        diferenca = abs(total_destino) - abs(total_origem)

        percentual_divergencia = abs(diferenca) / abs(total_origem) * 100 if total_origem else 0.0

        situacao = "CONCILIADO" if abs(diferenca) <= 0.01 else "DIVERGENTE"

        resumo = {
            "total_origem": round(total_origem, 2),
            "total_destino": round(total_destino, 2),
            "diferenca": round(diferenca, 2),
            "situacao": situacao,
            "percentual_divergencia": round(percentual_divergencia, 2),
            "quantidade_registros_origem": int(resumo_calc.get("total_registros", 0) or 0),
            "quantidade_registros_destino": int(resumo_calc.get("total_registros", 0) or 0),
            "data_processamento": datetime.now().isoformat(),
        }

        logger.info("✅ Resumo final: %s", resumo)

        # ==========================
        # 7️⃣ ANÁLISE DETALHADA (RESTAURO)
        # ==========================
        analise_detalhada = []
        analise_profunda_contabil = []
        resumo_analise = self._gerar_resumo_analise_fallback(df_completo)
        try:
            df_razao_geral = pd.DataFrame(request.base_contabil_geral.registros)
            df_razao_filtrado = self._filtrar_razao_por_conta(df_razao_geral, conta_contabil)

            analise_service = AnaliseDiferencasService()
            analise_detalhada = analise_service.processar_analise_detalhada(
                df_financeiro=financeiro_norm,
                df_contabilidade_filtrada=contabil_norm,
                df_razao_contabil=df_razao_filtrado,
                df_financeiro_detalhado=financeiro_detalhado,
                df_razao_geral=df_razao_geral,
                conta_contabil=conta_contabil,
            )

            if analise_detalhada:
                resumo_analise = analise_service.gerar_resumo_analise(analise_detalhada)
            else:
                # Mesmo sem análise, manter resumo coerente com o total calculado
                resumo_analise = self._formatar_resumo_analise(total=len(df_completo), conciliados=0)

            # ==========================
            # 7.1 ANÁLISE PROFUNDA SO_CONTABILIDADE
            # ==========================
            # DEBUG: Verificar tipos de diferença disponíveis
            tipos_encontrados = set(a.get("tipo_diferenca") for a in analise_detalhada)
            logger.info("🔍 Tipos de diferença encontrados: %s", tipos_encontrados)

            registros_so_contabilidade = [
                a for a in analise_detalhada
                if a.get("tipo_diferenca") == "SO_CONTABILIDADE"
            ]
            logger.info("🔍 Registros SO_CONTABILIDADE encontrados: %s", len(registros_so_contabilidade))

            if registros_so_contabilidade:
                logger.info(
                    "🔍 Iniciando análise profunda de %s registros SO_CONTABILIDADE",
                    len(registros_so_contabilidade)
                )
                analise_profunda_contabil = analise_service.analisar_so_contabilidade_profundo(
                    registros_so_contabilidade=registros_so_contabilidade,
                    df_razao_geral=df_razao_geral,  # Usa razão geral COMPLETO para buscar origens
                    conta_analisada=conta_contabil,
                )
                logger.info("✅ Análise profunda concluída: %s registros", len(analise_profunda_contabil))

        except Exception as exc:
            logger.error("❌ Falha ao gerar análise detalhada: %s", exc, exc_info=True)

        # ==========================
        # 8️⃣ RETORNO FINAL (DICT)
        # ==========================
        retorno = {
            "resumo": resumo,
            "diferencas_origem_maior": diferencas_origem_maior,
            "diferencas_contabilidade_maior": diferencas_contabilidade_maior,
            "analise_detalhada": analise_detalhada,
            "resumo_analise": resumo_analise,
            "analise_profunda_contabil": analise_profunda_contabil,
            "observacoes": [
                f"Total de {len(diferencas_origem_maior)} registros onde origem > contabilidade",
                f"Total de {len(diferencas_contabilidade_maior)} registros onde contabilidade > origem",
                f"Percentual de divergência: {percentual_divergencia:.2f}%",
                f"Total de {len(analise_profunda_contabil)} registros SO_CONTABILIDADE analisados em profundidade",
            ],
            "alertas": [
                "⚠️ Verificar diferenças significativas"
                if abs(diferenca) > 1000
                else "✅ Diferenças dentro do esperado"
            ],
        }

        logger.info("✅ Conciliação executada com sucesso")
        logger.info(
            "📦 Retorno final com %s origem_maior, %s contabil_maior, %s análise_detalhada, %s análise_profunda",
            len(diferencas_origem_maior),
            len(diferencas_contabilidade_maior),
            len(analise_detalhada),
            len(analise_profunda_contabil),
        )

        return retorno
