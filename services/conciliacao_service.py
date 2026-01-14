import logging
import pandas as pd
from datetime import datetime

from schemas.conciliacao_schema import RequestConciliacao, RelatorioConsolidacao
from tools.financeiro import normalizar_planilha_financeira
from tools.contabilidade import normalizar_planilha_contabilidade
from tools.calc_diferencas import calcular_diferencas
from tools.mappers import map_origem_maior, map_contabilidade_maior

logger = logging.getLogger(__name__)


class ConciliacaoService:

    # ==================================================
    # VALIDAÇÃO
    # ==================================================
    def validar_dados(self, request):
        if not request.base_origem or not request.base_origem.registros:
            return False, "Base de origem vazia"

        if not request.base_contabil_filtrada or not request.base_contabil_filtrada.registros:
            return False, "Base contábil filtrada vazia"

        if not request.base_contabil_geral or not request.base_contabil_geral.registros:
            return False, "Base geral da contabilidade vazia"

        if not request.parametros or not request.parametros.get("data_base"):
            return False, "Data-base não informada"

        return True, ""

    # ==================================================
    # EXECUÇÃO PRINCIPAL
    # ==================================================
    def executar(self, request: RequestConciliacao) -> dict:
        """
        Retorna dict ao invés de RelatorioConsolidacao para compatibilidade com frontend
        """
        logger.info("⚙️ Executando conciliação contábil")

        # ==========================
        # 1️⃣ NORMALIZAR FINANCEIRO
        # ==========================
        df_financeiro_raw = pd.DataFrame(request.base_origem.registros)
        logger.info(f"📊 Registros origem recebidos: {len(df_financeiro_raw)}")
        
        financeiro_norm = normalizar_planilha_financeira(df_financeiro_raw)
        logger.info(f"✅ Financeiro normalizado: {len(financeiro_norm)} registros")

        # ==========================
        # 2️⃣ NORMALIZAR CONTABILIDADE
        # ==========================
        df_contabil_raw = pd.DataFrame(request.base_contabil_filtrada.registros)
        logger.info(f"📊 Registros contábeis recebidos: {len(df_contabil_raw)}")
        
        contabil_norm = normalizar_planilha_contabilidade(df_contabil_raw)
        logger.info(f"✅ Contabilidade normalizada: {len(contabil_norm)} registros")

        # ==========================
        # 3️⃣ CALCULAR DIFERENÇAS
        # ==========================
        resultado = calcular_diferencas(
            df_financeiro=financeiro_norm,
            df_contabilidade=contabil_norm,
            salvar_arquivo=False
        )

        resumo_calc = resultado["resumo"]
        df_completo = resultado["df_completo"]

        logger.info(f"📈 Resumo calculado: {resumo_calc}")
        
        # Debug: mostrar colunas do DataFrame
        logger.info(f"🔍 Colunas do df_completo: {df_completo.columns.tolist()}")
        logger.info(f"🔍 Primeiras linhas:\n{df_completo.head()}")

        # ==========================
        # 4️⃣ FILTRAR DIFERENÇAS
        # ==========================
        # IMPORTANTE: Usar o nome correto da coluna "Tipo Diferença"
        df_origem_maior = df_completo[
            df_completo["Tipo Diferença"] == "Financeiro > Contabilidade"
        ].copy()
        
        df_contabil_maior = df_completo[
            df_completo["Tipo Diferença"] == "Contabilidade > Financeiro"
        ].copy()

        logger.info(f"📊 Diferenças Origem > Contábil: {len(df_origem_maior)}")
        logger.info(f"📊 Diferenças Contábil > Origem: {len(df_contabil_maior)}")

        # Debug: mostrar algumas linhas
        if len(df_origem_maior) > 0:
            logger.info(f"🔍 Amostra origem_maior:\n{df_origem_maior[['Código', 'Cliente', 'Valor Financeiro', 'Valor Contabilidade', 'Diferença']].head()}")
        
        if len(df_contabil_maior) > 0:
            logger.info(f"🔍 Amostra contabil_maior:\n{df_contabil_maior[['Código', 'Cliente', 'Valor Financeiro', 'Valor Contabilidade', 'Diferença']].head()}")

        # ==========================
        # 5️⃣ MAPEAR DIFERENÇAS (SCHEMA)
        # ==========================
        diferencas_origem_maior = []
        for row_dict in df_origem_maior.to_dict("records"):
            try:
                # row_dict é um dicionário com as colunas do DataFrame
                mapped = map_origem_maior(row_dict)
                diferencas_origem_maior.append(mapped)
            except Exception as e:
                logger.error(f"❌ Erro ao mapear origem_maior: {e}")
                logger.error(f"   Row problemático: {row_dict}")

        diferencas_contabilidade_maior = []
        for row_dict in df_contabil_maior.to_dict("records"):
            try:
                # row_dict é um dicionário, não um DataFrame
                mapped = map_contabilidade_maior(
                    row_dict,  # Passar o dict diretamente
                    request.base_contabil_filtrada.conta_contabil
                )
                diferencas_contabilidade_maior.append(mapped)
            except Exception as e:
                logger.error(f"❌ Erro ao mapear contabil_maior: {e}")
                logger.error(f"   Row problemático: {row_dict}")

        logger.info(f"✅ Mapeados: {len(diferencas_origem_maior)} origem_maior, {len(diferencas_contabilidade_maior)} contabil_maior")

        # ==========================
        # 6️⃣ RESUMO (FORMATO FRONTEND)
        # ==========================
        total_origem = float(resumo_calc.get("valor_total_financeiro", 0))
        total_destino = float(resumo_calc.get("valor_total_contabilidade", 0))
        diferenca = float(resumo_calc.get("diferenca_total", 0))

        percentual_divergencia = (
            abs(diferenca) / total_origem * 100
            if total_origem else 0.0
        )

        situacao = "CONCILIADO" if abs(diferenca) < 0.01 else "DIVERGENTE"

        resumo = {
            "total_origem": round(total_origem, 2),
            "total_destino": round(total_destino, 2),
            "diferenca": round(diferenca, 2),
            "situacao": situacao,
            "percentual_divergencia": round(percentual_divergencia, 2),
            "quantidade_registros_origem": int(resumo_calc.get("total_registros", 0)),
            "quantidade_registros_destino": int(resumo_calc.get("total_registros", 0)),
            "data_processamento": datetime.now().isoformat()
        }

        logger.info(f"✅ Resumo final: {resumo}")

        # ==========================
        # 7️⃣ RETORNO FINAL (DICT)
        # ==========================
        retorno = {
            "resumo": resumo,
            "diferencas_origem_maior": diferencas_origem_maior,
            "diferencas_contabilidade_maior": diferencas_contabilidade_maior,
            "observacoes": [
                f"Total de {len(diferencas_origem_maior)} registros onde origem > contabilidade",
                f"Total de {len(diferencas_contabilidade_maior)} registros onde contabilidade > origem",
                f"Percentual de divergência: {percentual_divergencia:.2f}%"
            ],
            "alertas": [
                "⚠️ Verificar diferenças significativas" if abs(diferenca) > 1000 else "✅ Diferenças dentro do esperado"
            ]
        }

        logger.info("✅ Conciliação executada com sucesso")
        logger.info(f"📦 Retorno final com {len(diferencas_origem_maior)} origem_maior e {len(diferencas_contabilidade_maior)} contabil_maior")
        
        return retorno