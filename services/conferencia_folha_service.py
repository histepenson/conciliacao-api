import calendar
import logging
from itertools import combinations
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.situacoes_folha import SituacaoConferenciaFolha
from models.planodecontas import PlanoDeContas
from schemas.conferencia_folha_schema import ContaConferenciaFolha, ResultadoContaFolha
from schemas.folha_pagamento_schema import GrupoFolhaResultado
from services.ctbr480_service import Ctbr480Service
from services.folha_pagamento_service import FolhaPagamentoService

logger = logging.getLogger(__name__)

# Mesmo threshold de conciliacao usado no restante do sistema (ver CLAUDE.md).
THRESHOLD_CONCILIADO = 0.01

# Segunda etapa do matching (so' roda quando o total nao bate de cara):
# tenta achar 1..N lancamentos do razao cuja soma (debito - credito) fecha
# com o total_esperado - mesma logica de combinacoes usada em
# services/estrategias/bbc/leasing_matching.py::_tentar_casar, duplicada
# aqui (em vez de importada) porque aquele modulo e' especifico da
# estrategia BBC/leasing e nao deveria ser dependencia da Conferencia Folha.
MAX_ITENS_BUSCA_VALOR = 4


def _buscar_combinacao_valor(valor_alvo: float, linhas: list[dict[str, Any]]) -> Optional[list[dict[str, Any]]]:
    alvo_centavos = round(valor_alvo * 100)
    if alvo_centavos == 0:
        return []
    candidatos = [
        (idx, float(l.get("debito") or 0) - float(l.get("credito") or 0))
        for idx, l in enumerate(linhas)
    ]
    for tamanho in range(1, min(MAX_ITENS_BUSCA_VALOR, len(candidatos)) + 1):
        for combo in combinations(candidatos, tamanho):
            soma_centavos = round(sum(v for _, v in combo) * 100)
            if abs(soma_centavos - alvo_centavos) <= 1:
                return [linhas[idx] for idx, _ in combo]
    return None


class ContaFolhaNaoConfiguradaError(Exception):
    pass


def listar_contas_configuradas(db: Session, empresa_id: int) -> list[ContaConferenciaFolha]:
    """Contas do plano de contas com uma situacao de Conferencia Folha vinculada."""
    contas = (
        db.query(PlanoDeContas)
        .filter(
            PlanoDeContas.empresa_id == empresa_id,
            PlanoDeContas.situacao_conferencia_folha.isnot(None),
        )
        .order_by(PlanoDeContas.conta_contabil)
        .all()
    )
    return [
        ContaConferenciaFolha(
            id=c.id,
            conta_contabil=c.conta_contabil,
            descricao=c.descricao,
            situacao_conferencia_folha=c.situacao_conferencia_folha,
        )
        for c in contas
    ]


class ConferenciaFolhaService:
    """
    Motor da Conferencia Folha: para cada conta com situacao vinculada, busca o
    detalhamento da situacao (ZFOLPAGAPI), busca o saldo do razao da conta no
    periodo (ZCT2RAZAPI) e calcula a diferenca. Nao estende ConciliacaoService
    porque nao e o fluxo receber/pagar item-a-item - aqui e "total calculado x
    saldo da conta".
    """

    def __init__(self, folha_service: FolhaPagamentoService, razao_service: Ctbr480Service):
        self._folha_service = folha_service
        self._razao_service = razao_service

    async def executar_conta(
        self,
        db: Session,
        empresa_id: int,
        conta_id: int,
        periodo: str,
        filtros: dict[str, Any],
    ) -> ResultadoContaFolha:
        conta = (
            db.query(PlanoDeContas)
            .filter(PlanoDeContas.id == conta_id, PlanoDeContas.empresa_id == empresa_id)
            .first()
        )
        if not conta or not conta.situacao_conferencia_folha:
            raise ContaFolhaNaoConfiguradaError(f"Conta {conta_id} nao esta configurada para Conferencia Folha")

        situacao = SituacaoConferenciaFolha(conta.situacao_conferencia_folha)

        detalhe = await self._folha_service.buscar_situacao(situacao, filtros)
        saldo_razao, razao_linhas = await self._buscar_razao(conta.conta_contabil, periodo)

        total_esperado = float(detalhe.get("total_geral") or 0)
        diferenca = abs(total_esperado - saldo_razao)
        grupos = [GrupoFolhaResultado(**g) for g in detalhe.get("grupos", [])]
        status = "ok" if diferenca <= THRESHOLD_CONCILIADO else "diferente"

        matching_valor_linhas = None
        if status == "diferente":
            matching_valor_linhas = _buscar_combinacao_valor(total_esperado, razao_linhas)

        return ResultadoContaFolha(
            conta_id=conta.id,
            conta_contabil=conta.conta_contabil,
            descricao=conta.descricao,
            situacao=situacao.value,
            parametros=detalhe.get("parametros", {}),
            grupos=grupos,
            total_esperado=total_esperado,
            saldo_razao=saldo_razao,
            razao_linhas=razao_linhas,
            diferenca=diferenca,
            status=status,
            total_registros=int(detalhe.get("total_registros") or 0),
            matching_valor_linhas=matching_valor_linhas,
        )

    async def _buscar_razao(self, conta_contabil: str, periodo: str) -> tuple[float, list[dict[str, Any]]]:
        """
        Busca os lancamentos do razao da conta no periodo informado e soma
        (debito - credito). As contas de folha sao passivo (natureza
        credora): credito e quando o passivo e gerado (provisao), debito e
        quando e baixado/pago - e e o debito que corresponde ao
        "total_esperado" (soma dos titulos baixados no periodo), entao o
        saldo aqui precisa ficar na mesma convencao de sinal (positivo) para
        a diferenca fazer sentido. O ZCT2RAZAPI nao calcula saldo corrente
        (campo saldo_atual sempre 0), entao o saldo precisa ser derivado
        aqui a partir dos lancamentos. As linhas cruas tambem sao devolvidas
        para exibir o lado "razao" do drill-down (mesmo padrao das telas de
        conciliacao financeiro x contabil).
        """
        ano, mes = periodo.split("-")
        data_ini = f"{ano}{mes.zfill(2)}01"
        ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
        data_fim = f"{ano}{mes.zfill(2)}{ultimo_dia:02d}"

        registros = await self._razao_service.buscar_como_registros({
            "data_ini": data_ini,
            "data_fim": data_fim,
            "conta_de": conta_contabil,
            "conta_ate": conta_contabil,
            # consid_filiais=1 sem filial_de/filial_ate = todas as filiais da
            # empresa (default do ZCT2RAZAPI e' 2 = so' filial corrente da
            # conexao, o que ficaria inconsistente com o lado financeiro do
            # ZFOLPAGAPI, que tambem nao restringe por filial).
            "consid_filiais": "1",
        })

        registros_da_conta = [
            r for r in registros if str(r.get("conta", "")).strip() == conta_contabil.strip()
        ]
        saldo = sum(
            float(r.get("debito") or 0) - float(r.get("credito") or 0)
            for r in registros_da_conta
        )
        return abs(saldo), registros_da_conta
