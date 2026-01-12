from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class BaseOrigem(BaseModel):
    registros: List[Dict[str, Any]]

class BaseContabilFiltrada(BaseModel):
    registros: List[Dict[str, Any]]
    conta_contabil: str

class BaseContabilGeral(BaseModel):
    registros: List[Dict[str, Any]]

class RequestConciliacao(BaseModel):
    base_origem: BaseOrigem
    base_contabil_filtrada: BaseContabilFiltrada
    base_contabil_geral: BaseContabilGeral
    parametros: Optional[Dict[str, Any]] = Field(default_factory=dict)
