"""
Service para o Dashboard.
"""
import logging
from datetime import datetime, timezone
from typing import List
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from models import Conciliacao, PlanoDeContas, Empresa
from schemas.dashboard_schema import (
    DashboardStats,
    ConciliacaoRecente,
    GraficoMensal,
    AlertaPendencia,
    DashboardResponse,
)
from schemas.efetivacao_schema import StatusConciliacao

logger = logging.getLogger(__name__)


class DashboardService:
    """Service para gerenciar dados do dashboard."""

    def _get_saudacao(self) -> str:
        """Retorna saudacao baseada na hora atual."""
        hora = datetime.now().hour
        if hora < 12:
            return "Bom dia"
        elif hora < 18:
            return "Boa tarde"
        else:
            return "Boa noite"

    def _get_data_formatada(self) -> str:
        """Retorna data atual formatada."""
        meses = [
            "", "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
            "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
        ]
        dias_semana = [
            "segunda-feira", "terca-feira", "quarta-feira",
            "quinta-feira", "sexta-feira", "sabado", "domingo"
        ]

        agora = datetime.now()
        dia_semana = dias_semana[agora.weekday()]
        dia = agora.day
        mes = meses[agora.month]
        ano = agora.year

        return f"{dia_semana}, {dia} de {mes} de {ano}"

    def _get_stats(self, db: Session, empresa_id: int) -> DashboardStats:
        """Calcula estatisticas da empresa."""
        # Total de contas conciliaveis
        total_contas = db.query(PlanoDeContas).filter(
            PlanoDeContas.empresa_id == empresa_id,
            PlanoDeContas.conciliavel == True
        ).count()

        # Mes atual
        agora = datetime.now()
        periodo_atual = f"{agora.year}-{agora.month:02d}"

        # Contas conciliadas no mes atual
        contas_conciliadas = db.query(Conciliacao).filter(
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.periodo == periodo_atual,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        ).count()

        # Contas pendentes
        contas_pendentes = total_contas - contas_conciliadas
        if contas_pendentes < 0:
            contas_pendentes = 0

        # Taxa de sucesso
        taxa_sucesso = 0.0
        if total_contas > 0:
            taxa_sucesso = round((contas_conciliadas / total_contas) * 100, 1)

        return DashboardStats(
            total_contas=total_contas,
            contas_conciliadas=contas_conciliadas,
            contas_pendentes=contas_pendentes,
            taxa_sucesso=taxa_sucesso
        )

    def _get_conciliacoes_recentes(
        self, db: Session, empresa_id: int, limit: int = 5
    ) -> List[ConciliacaoRecente]:
        """Retorna as ultimas conciliacoes efetivadas."""
        conciliacoes = db.query(Conciliacao).filter(
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        ).order_by(
            Conciliacao.data_efetivacao.desc()
        ).limit(limit).all()

        items = []
        for c in conciliacoes:
            resumo = c.resultado_json.get("resumo", {}) if c.resultado_json else {}
            items.append(ConciliacaoRecente(
                id=c.id,
                conta_contabil=c.conta_contabil.conta_contabil if c.conta_contabil else "",
                descricao=c.conta_contabil.descricao if c.conta_contabil else "",
                periodo=c.periodo,
                data_efetivacao=c.data_efetivacao,
                situacao=resumo.get("situacao", "CONCILIADO")
            ))

        return items

    def _get_grafico_mensal(
        self, db: Session, empresa_id: int, meses: int = 6
    ) -> List[GraficoMensal]:
        """Retorna dados para grafico de conciliacoes por mes."""
        nomes_meses = [
            "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
            "Jul", "Ago", "Set", "Out", "Nov", "Dez"
        ]

        resultado = []
        agora = datetime.now()

        for i in range(meses - 1, -1, -1):
            data = agora - relativedelta(months=i)
            periodo = f"{data.year}-{data.month:02d}"

            quantidade = db.query(Conciliacao).filter(
                Conciliacao.empresa_id == empresa_id,
                Conciliacao.periodo == periodo,
                Conciliacao.status == StatusConciliacao.EFETIVADA.value
            ).count()

            resultado.append(GraficoMensal(
                mes=nomes_meses[data.month],
                ano=data.year,
                quantidade=quantidade
            ))

        return resultado

    def _get_alertas(
        self, db: Session, empresa_id: int
    ) -> List[AlertaPendencia]:
        """Retorna alertas e pendencias."""
        alertas = []
        agora = datetime.now()
        periodo_atual = f"{agora.year}-{agora.month:02d}"

        # Total de contas conciliaveis
        total_contas = db.query(PlanoDeContas).filter(
            PlanoDeContas.empresa_id == empresa_id,
            PlanoDeContas.conciliavel == True
        ).count()

        # Contas conciliadas no mes atual
        contas_conciliadas = db.query(Conciliacao).filter(
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.periodo == periodo_atual,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        ).count()

        pendentes = total_contas - contas_conciliadas

        if pendentes > 0:
            alertas.append(AlertaPendencia(
                tipo="warning",
                mensagem=f"{pendentes} conta(s) pendente(s) de conciliacao este mes",
                acao_url="/conciliacoes/periodo"
            ))

        # Verificar mes anterior
        mes_anterior = agora - relativedelta(months=1)
        periodo_anterior = f"{mes_anterior.year}-{mes_anterior.month:02d}"

        contas_mes_anterior = db.query(Conciliacao).filter(
            Conciliacao.empresa_id == empresa_id,
            Conciliacao.periodo == periodo_anterior,
            Conciliacao.status == StatusConciliacao.EFETIVADA.value
        ).count()

        if contas_mes_anterior < total_contas and total_contas > 0:
            faltantes = total_contas - contas_mes_anterior
            nomes_meses = [
                "", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
            ]
            alertas.append(AlertaPendencia(
                tipo="info",
                mensagem=f"Fechamento de {nomes_meses[mes_anterior.month]} incompleto ({faltantes} conta(s))",
                acao_url="/acompanhamento-fechamentos"
            ))

        if not alertas:
            alertas.append(AlertaPendencia(
                tipo="success",
                mensagem="Todas as conciliacoes estao em dia!",
                acao_url=None
            ))

        return alertas

    def get_dashboard(
        self, db: Session, empresa_id: int, user_nome: str
    ) -> DashboardResponse:
        """Retorna todos os dados do dashboard."""
        # Buscar nome da empresa
        empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        empresa_nome = empresa.nome if empresa else "Empresa"

        return DashboardResponse(
            saudacao=f"{self._get_saudacao()}, {user_nome}!",
            data_atual=self._get_data_formatada(),
            empresa_nome=empresa_nome,
            stats=self._get_stats(db, empresa_id),
            conciliacoes_recentes=self._get_conciliacoes_recentes(db, empresa_id),
            grafico_mensal=self._get_grafico_mensal(db, empresa_id),
            alertas=self._get_alertas(db, empresa_id)
        )
