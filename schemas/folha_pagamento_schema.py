from typing import Any, Literal, Optional

from pydantic import BaseModel


class GrupoFolhaResultado(BaseModel):
    """Um grupo de linhas de origem (SE2 ou SRD) que compoe o total de uma situacao."""
    fonte: Literal["SE2", "SRD"]
    campo_valor: str
    total: float
    linhas: list[dict[str, Any]]


class FolhaSituacaoResponse(BaseModel):
    """Resposta de um dos 12 wsmethods do ZFOLPAGAPI.prw."""
    situacao: str
    conta_contabil: str
    parametros: dict[str, Any] = {}
    grupos: list[GrupoFolhaResultado]
    total_geral: float
    total_registros: int


class FolhaErroResponse(BaseModel):
    error: str
    message: str
    details: Optional[str] = None
