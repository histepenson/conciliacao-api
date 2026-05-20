from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProtheusCargaConfigBase(BaseModel):
    tipo_relatorio: str = Field(..., max_length=30)
    nome: str = Field(..., max_length=150)
    parametros_json: dict[str, Any] = Field(default_factory=dict)
    ativo: bool = True
    atualizar_automatico: bool = True
    data_base_origem: str = "periodo_aberto"
    data_base_fixa: Optional[str] = Field(default=None, max_length=8)


class ProtheusCargaConfigCreate(ProtheusCargaConfigBase):
    empresa_id: Optional[int] = None


class ProtheusCargaConfigUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, max_length=150)
    parametros_json: Optional[dict[str, Any]] = None
    ativo: Optional[bool] = None
    atualizar_automatico: Optional[bool] = None
    data_base_origem: Optional[str] = None
    data_base_fixa: Optional[str] = Field(default=None, max_length=8)


class ProtheusCargaConfigOut(ProtheusCargaConfigBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    empresa_id: int
    created_at: datetime
    updated_at: datetime


class ProtheusCargaCreate(BaseModel):
    empresa_id: Optional[int] = None
    tipo_relatorio: str = Field(..., max_length=30)
    data_base: str = Field(..., min_length=8, max_length=8)
    parametros_json: dict[str, Any] = Field(default_factory=dict)
    config_id: Optional[int] = None


class ProtheusCargaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    config_id: Optional[int]
    empresa_id: int
    tipo_relatorio: str
    data_base: str
    parametros_hash: str
    parametros_json: dict[str, Any]
    status: str
    total_registros: int
    iniciado_em: Optional[datetime]
    finalizado_em: Optional[datetime]
    erro: Optional[str]
    rq_job_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class ProtheusCargaRegistroOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    carga_id: int
    sequencia: int
    dados_json: dict[str, Any]
    created_at: datetime


class ProtheusCargaRegistrosPage(BaseModel):
    total: int
    skip: int
    limit: int
    registros: list[ProtheusCargaRegistroOut]


class ProtheusCargaEnfileirada(BaseModel):
    carga: ProtheusCargaOut
    reutilizavel: bool = False
    mensagem: str
