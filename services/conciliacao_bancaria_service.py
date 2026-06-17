"""
Servico de Conciliacao Bancaria.

Orquestra o fluxo de conciliacao entre extrato bancario (FINR470)
e razao contabil de banco (CTBR400).
"""

import logging
from datetime import datetime
from typing import Dict, Any

import pandas as pd

from schemas.conciliacao_bancaria_schema import RequestConciliacaoBancaria
from tools.banco.extrato_bancario import normalizar_extrato_bancario
from tools.banco.razao_banco import normalizar_razao_banco
from tools.banco.calc_diferencas_banco import calcular_diferencas_bancarias

logger = logging.getLogger(__name__)


class ConciliacaoBancariaService:
    """Servico para processar conciliacao bancaria."""

    def validar_dados(self, request: RequestConciliacaoBancaria) -> tuple[bool, str]:
        """Valida os dados de entrada."""
        if not request.base_extrato or not request.base_extrato.registros:
            return False, "Base do extrato bancario vazia"

        if not request.base_razao or not request.base_razao.registros:
            return False, "Base do razao contabil vazia"

        if not request.parametros or not request.parametros.data_base:
            return False, "Data-base nao informada"

        return True, ""

    def executar(self, request: RequestConciliacaoBancaria) -> Dict[str, Any]:
        """
        Executa a conciliacao bancaria agrupada por dia.

        Fluxo:
        1. Normaliza extrato bancario (FINR470)
        2. Normaliza razao contabil (CTBR400)
        3. Agrupa por dia e calcula diferencas
        4. Gera relatorio

        Returns:
            Dict com relatorio completo da conciliacao
        """
        logger.info("=" * 50)
        logger.info("CONCILIACAO BANCARIA - INICIO")
        logger.info("=" * 50)

        # ==========================
        # 1. NORMALIZAR EXTRATO
        # ==========================
        logger.info("[1/3] Normalizando extrato bancario (FINR470)")

        df_extrato_raw = pd.DataFrame(request.base_extrato.registros)
        logger.info(f"   Registros recebidos: {len(df_extrato_raw)}")

        try:
            df_extrato = normalizar_extrato_bancario(df_extrato_raw)
            logger.info(f"   Movimentos normalizados: {len(df_extrato)}")
        except Exception as e:
            logger.error(f"   ERRO ao normalizar extrato: {str(e)}")
            raise ValueError(f"Erro ao processar extrato bancario: {str(e)}")

        # ==========================
        # 2. NORMALIZAR RAZAO
        # ==========================
        logger.info("[2/3] Normalizando razao contabil (CTBR400)")

        df_razao_raw = pd.DataFrame(request.base_razao.registros)
        logger.info(f"   Registros recebidos: {len(df_razao_raw)}")

        try:
            df_razao = normalizar_razao_banco(df_razao_raw)
            logger.info(f"   Lancamentos normalizados: {len(df_razao)}")
        except Exception as e:
            logger.error(f"   ERRO ao normalizar razao: {str(e)}")
            raise ValueError(f"Erro ao processar razao contabil: {str(e)}")

        # ==========================
        # 3. CALCULAR DIFERENCAS POR DIA
        # ==========================
        logger.info("[3/3] Calculando diferencas por dia")

        resultado = calcular_diferencas_bancarias(
            df_extrato=df_extrato,
            df_razao=df_razao
        )

        resumo = resultado["resumo"]
        logger.info(f"   Dias analisados: {resumo['qtd_dias']}")
        logger.info(f"   Dias conciliados: {resumo['qtd_conciliados']}")
        logger.info(f"   Dias divergentes: {resumo['qtd_divergentes']}")

        # ==========================
        # 4. MONTAR RESPOSTA
        # ==========================
        conta_contabil = request.base_razao.conta_contabil

        # Contar registros sem correspondencia
        qtd_so_extrato = len(resultado.get("registros_so_extrato", []))
        qtd_so_razao = len(resultado.get("registros_so_razao", []))

        resposta = {
            "resumo": resumo,
            "movimentos_por_dia": resultado["movimentos_por_dia"],
            "dias_divergentes": resultado["dias_divergentes"],
            "dias_conciliados": resultado["dias_conciliados"],
            # Registros detalhados sem correspondencia
            "registros_so_extrato": resultado.get("registros_so_extrato", []),
            "registros_so_razao": resultado.get("registros_so_razao", []),
            "observacoes": [
                f"Conciliacao bancaria da conta {conta_contabil}",
                f"Data-base: {request.parametros.data_base}",
                f"Total de {resumo['qtd_dias']} dias analisados",
                f"Percentual de conciliacao: {resumo['percentual_conciliacao']:.2f}%",
            ],
            "alertas": self._gerar_alertas(resumo, qtd_so_extrato, qtd_so_razao),
        }

        logger.info("=" * 50)
        logger.info(f"CONCILIACAO BANCARIA - {resumo['situacao']}")
        logger.info("=" * 50)

        return resposta

    def _gerar_alertas(self, resumo: Dict[str, Any], qtd_so_extrato: int = 0, qtd_so_razao: int = 0) -> list:
        """Gera alertas baseados no resumo da conciliacao."""
        alertas = []

        if resumo.get("saldo_final_bate"):
            alertas.append(
                "Saldo final do periodo bate entre extrato e razao - "
                "conciliacao considerada OK mesmo com diferencas pontuais por dia"
            )
            return alertas

        if resumo["qtd_divergentes"] > 0:
            alertas.append(
                f"ATENCAO: {resumo['qtd_divergentes']} dia(s) com divergencia"
            )

        if abs(resumo["dif_total_entradas"]) > 0.01:
            alertas.append(
                f"Diferenca nas entradas: R$ {resumo['dif_total_entradas']:,.2f}"
            )

        if abs(resumo["dif_total_saidas"]) > 0.01:
            alertas.append(
                f"Diferenca nas saidas: R$ {resumo['dif_total_saidas']:,.2f}"
            )

        if qtd_so_extrato > 0:
            alertas.append(
                f"{qtd_so_extrato} registro(s) no extrato sem correspondencia no razao"
            )

        if qtd_so_razao > 0:
            alertas.append(
                f"{qtd_so_razao} registro(s) no razao sem correspondencia no extrato"
            )

        if resumo["percentual_conciliacao"] < 100:
            alertas.append(
                f"Verificar dias divergentes para identificar lancamentos faltantes"
            )

        if not alertas:
            alertas.append("Conciliacao OK - Todos os dias conferem")

        return alertas
