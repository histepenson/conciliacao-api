from typing import Any, Literal

from pydantic import BaseModel


class AnalisarDivergenciaBody(BaseModel):
    """
    Rota generica (financeiro/bancario/estoque): o frontend ja tem o
    resultado completo da conciliacao em memoria (sem nenhum filtro de
    config removendo candidatos antes do match, diferente do fiscal), por
    isso so' reencaminha os registros nao-conciliados de cada lado.
    """
    dominio: Literal["financeiro", "bancario", "estoque"]
    contexto: dict[str, Any] = {}
    registros_nao_conciliados_a: list[dict[str, Any]] = []
    registros_nao_conciliados_b: list[dict[str, Any]] = []
    rotulo_a: str = "Lado A"
    rotulo_b: str = "Lado B"
