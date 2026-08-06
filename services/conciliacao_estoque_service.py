"""
Servico de Conciliacao de Estoque.

Orquestra o fluxo de conciliacao entre Kardex (movimentacao de estoque)
e razao contabil de estoque (CTBR400).
"""

import logging
from datetime import datetime
from typing import Dict, Any

import pandas as pd

from core.data_base import parse_ano_mes
from schemas.conciliacao_estoque_schema import RequestConciliacaoEstoque
from tools.estoque.kardex import normalizar_kardex
from tools.estoque.razao_estoque import normalizar_razao_estoque
from tools.estoque.calc_diferencas_estoque import calcular_diferencas_estoque

logger = logging.getLogger(__name__)


class ConciliacaoEstoqueService:
    """Servico para processar conciliacao de estoque."""

    def validar_dados(self, request: RequestConciliacaoEstoque) -> tuple[bool, str]:
        """Valida os dados de entrada."""
        if not request.base_kardex or not request.base_kardex.registros:
            return False, "Base do Kardex vazia"

        if not request.base_razao or not request.base_razao.registros:
            return False, "Base do razao contabil vazia"

        if not request.parametros or not request.parametros.data_base:
            return False, "Data-base nao informada"

        return True, ""

    def _extrair_ano_base(self, data_base: str) -> int:
        """Extrai o ano da data_base (DD/MM/YYYY, MM/YYYY ou YYYYMMDD)."""
        try:
            ano, _mes = parse_ano_mes(data_base)
            return ano
        except ValueError:
            return datetime.now().year

    def executar(self, request: RequestConciliacaoEstoque) -> Dict[str, Any]:
        """
        Executa a conciliacao de estoque.

        Fluxo:
        1. Normaliza Kardex
        2. Normaliza Razao Contabil de Estoque (CTBR400)
        3. Agrupa por (data, codigo_movimento) e calcula diferencas
        4. Gera relatorio

        Returns:
            Dict com relatorio completo da conciliacao
        """
        logger.info("=" * 50)
        logger.info("CONCILIACAO ESTOQUE - INICIO")
        logger.info("=" * 50)

        ano_base = self._extrair_ano_base(request.parametros.data_base)

        # ==========================
        # 1. NORMALIZAR KARDEX
        # ==========================
        logger.info("[1/3] Normalizando Kardex")

        df_kardex_raw = pd.DataFrame(request.base_kardex.registros)
        logger.info(f"   Registros recebidos: {len(df_kardex_raw)}")

        try:
            df_kardex = normalizar_kardex(df_kardex_raw)
            logger.info(f"   Movimentos normalizados: {len(df_kardex)}")
        except Exception as e:
            logger.error(f"   ERRO ao normalizar Kardex: {str(e)}")
            raise ValueError(f"Erro ao processar Kardex: {str(e)}")

        logger.info(f"   Ano-base para extracao de data no Razao (parametro): {ano_base}")

        # ==========================
        # 2. NORMALIZAR RAZAO
        # ==========================
        logger.info("[2/3] Normalizando Razao Contabil de Estoque (CTBR400)")

        df_razao_raw = pd.DataFrame(request.base_razao.registros)
        logger.info(f"   Registros recebidos: {len(df_razao_raw)}")

        try:
            df_razao = normalizar_razao_estoque(df_razao_raw, ano_base=ano_base)
            logger.info(f"   Lancamentos normalizados: {len(df_razao)}")
        except Exception as e:
            logger.error(f"   ERRO ao normalizar Razao: {str(e)}")
            raise ValueError(f"Erro ao processar Razao Contabil: {str(e)}")

        # ==========================
        # 3. CALCULAR DIFERENCAS
        # ==========================
        logger.info("[3/3] Calculando diferencas por (data, codigo_movimento)")

        resultado = calcular_diferencas_estoque(
            df_kardex=df_kardex,
            df_razao=df_razao
        )

        resumo = resultado["resumo"]
        logger.info(f"   Grupos analisados: {resumo['qtd_grupos']}")
        logger.info(f"   Grupos conciliados: {resumo['qtd_conciliados']}")
        logger.info(f"   Grupos divergentes: {resumo['qtd_divergentes']}")

        # ==========================
        # 4. MONTAR RESPOSTA
        # ==========================
        conta_contabil = request.base_razao.conta_contabil

        resposta = {
            "resumo": resumo,
            "movimentos_por_grupo": resultado["movimentos_por_grupo"],
            "grupos_divergentes": resultado["grupos_divergentes"],
            "grupos_conciliados": resultado["grupos_conciliados"],
            "observacoes": [
                f"Conciliacao de estoque da conta {conta_contabil}",
                f"Data-base: {request.parametros.data_base}",
                f"Total de {resumo['qtd_grupos']} grupos (data + movimento) analisados",
                f"Percentual de conciliacao: {resumo['percentual_conciliacao']:.2f}%",
            ],
            "alertas": self._gerar_alertas(resumo),
        }

        logger.info("=" * 50)
        logger.info(f"CONCILIACAO ESTOQUE - {resumo['situacao']}")
        logger.info("=" * 50)

        return resposta

    def _gerar_alertas(self, resumo: Dict[str, Any]) -> list:
        """Gera alertas baseados no resumo da conciliacao."""
        alertas = []

        if resumo["qtd_divergentes"] > 0:
            alertas.append(
                f"ATENCAO: {resumo['qtd_divergentes']} grupo(s) com divergencia"
            )

        if abs(resumo["dif_total"]) > 0.01:
            alertas.append(
                f"Diferenca total: R$ {resumo['dif_total']:,.2f}"
            )

        if resumo["qtd_so_kardex"] > 0:
            alertas.append(
                f"{resumo['qtd_so_kardex']} grupo(s) apenas no Kardex (sem correspondencia no Razao)"
            )

        if resumo["qtd_so_razao"] > 0:
            alertas.append(
                f"{resumo['qtd_so_razao']} grupo(s) apenas no Razao (sem correspondencia no Kardex)"
            )

        if resumo["percentual_conciliacao"] < 100:
            alertas.append(
                "Verificar grupos divergentes para identificar lancamentos faltantes"
            )

        if not alertas:
            alertas.append("Conciliacao OK - Todos os grupos conferem")

        return alertas
