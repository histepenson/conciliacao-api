# core/situacoes_folha.py
"""
Catalogo fechado das 12 situacoes de Conferencia Folha.

Cada situacao corresponde a uma consulta SQL validada pelo analista que
concilia a folha de pagamento hoje, e a um wsmethod especifico do novo
ZFOLPAGAPI.prw (protheus/ZFOLPAGAPI.prw). As 12 situacoes sao identicas
para Rancheiro e Ander (mesma conta contabil e natureza) - so a tabela
fisica e a filial mudam por tenant, resolvidas dinamicamente no .prw.

Fonte unica da verdade usada por: routers/folha_pagamento_router.py,
schemas/planodecontas_schema.py (campo situacao_conferencia_folha) e
services/conferencia_folha_service.py.
"""
from enum import Enum


class SituacaoConferenciaFolha(str, Enum):
    EMPRESTIMO_FUNCIONARIO = "emprestimo-funcionario"
    ADIANTAMENTO_FERIAS = "adiantamento-ferias"
    ADIANTAMENTO_RESCISAO = "adiantamento-rescisao"
    FGTS = "fgts"
    IRRF = "irrf"
    INSS = "inss"
    FGTS_RESCISORIO = "fgts-rescisorio"
    CONTRIBUICAO_ASSISTENCIAL = "contribuicao-assistencial"
    SALARIO = "salario"
    FERIAS_A_PAGAR = "ferias-a-pagar"
    PENSAO_ALIMENTICIA = "pensao-alimenticia"
    PLR = "plr"


# Conta contabil de referencia de cada situacao (identica para Rancheiro e Ander).
CONTA_POR_SITUACAO: dict[SituacaoConferenciaFolha, str] = {
    SituacaoConferenciaFolha.EMPRESTIMO_FUNCIONARIO: "11203004",
    SituacaoConferenciaFolha.ADIANTAMENTO_FERIAS: "11203006",
    SituacaoConferenciaFolha.ADIANTAMENTO_RESCISAO: "11203009",
    SituacaoConferenciaFolha.FGTS: "21102004",
    SituacaoConferenciaFolha.IRRF: "21102007",
    SituacaoConferenciaFolha.INSS: "21102010",
    SituacaoConferenciaFolha.FGTS_RESCISORIO: "21102013",
    SituacaoConferenciaFolha.CONTRIBUICAO_ASSISTENCIAL: "21102015",
    SituacaoConferenciaFolha.SALARIO: "21103001",
    SituacaoConferenciaFolha.FERIAS_A_PAGAR: "21103009",
    SituacaoConferenciaFolha.PENSAO_ALIMENTICIA: "21103011",
    SituacaoConferenciaFolha.PLR: "21103013",
}
