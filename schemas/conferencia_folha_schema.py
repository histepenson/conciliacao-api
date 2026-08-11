from typing import Any, Literal

from pydantic import BaseModel

from schemas.folha_pagamento_schema import GrupoFolhaResultado


class ContaConferenciaFolha(BaseModel):
    """Uma conta do plano de contas vinculada a uma situacao de Conferencia Folha."""
    id: int
    conta_contabil: str
    descricao: str
    situacao_conferencia_folha: str


class ContasConferenciaFolhaResponse(BaseModel):
    contas: list[ContaConferenciaFolha]


class ExecutarContaFolhaRequest(BaseModel):
    """Filtros manuais informados pelo usuario para processar uma linha da Conferencia Folha."""
    periodo: str  # "YYYY-MM", usado para buscar o saldo do razao no periodo
    filtros: dict[str, str] = {}


class ResultadoContaFolha(BaseModel):
    conta_id: int
    conta_contabil: str
    descricao: str
    situacao: str
    parametros: dict[str, Any] = {}
    grupos: list[GrupoFolhaResultado]
    total_esperado: float
    saldo_razao: float
    razao_linhas: list[dict[str, Any]] = []
    diferenca: float
    status: Literal["ok", "diferente"]
    total_registros: int
    # Segunda etapa do matching: so' preenchido quando status="diferente".
    # None = nao tentou (status ok); [] = tentou e nao achou combinacao;
    # lista no-vazia = subconjunto do razao_linhas que fecha com total_esperado.
    matching_valor_linhas: list[dict[str, Any]] | None = None
