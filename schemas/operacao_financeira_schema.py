from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# Catalogo fechado de modalidades validas (extensivel conforme novos
# modulos passem a usar o cadastro de Operacao Financeira). Hoje so'
# existe a Conferencia LEASING.
MODALIDADES_VALIDAS = ("LEASING",)


class OperacaoFinanceiraBase(BaseModel):
    empresa_id: Optional[int] = None
    codigo: str
    descricao: str
    tipo_lancamento: str
    modalidade: Optional[str] = "LEASING"
    ativo: bool = True

    @field_validator("tipo_lancamento")
    @classmethod
    def validar_tipo_lancamento(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v not in ("D", "C"):
            raise ValueError("tipo_lancamento deve ser 'D' ou 'C'")
        return v

    @field_validator("modalidade")
    @classmethod
    def validar_modalidade(cls, v: Optional[str]) -> Optional[str]:
        # Nula e' valida (natureza inativa fica sem modalidade, ver
        # services/operacao_financeira_service.py). So' valida o
        # catalogo quando um valor de fato vier preenchido.
        if v is None or not v.strip():
            return None
        v = v.strip().upper()
        if v not in MODALIDADES_VALIDAS:
            raise ValueError(f"modalidade deve ser uma de: {', '.join(MODALIDADES_VALIDAS)}")
        return v


class OperacaoFinanceiraCreate(OperacaoFinanceiraBase):
    pass


class OperacaoFinanceiraUpdate(BaseModel):
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    tipo_lancamento: Optional[str] = None
    modalidade: Optional[str] = None
    ativo: Optional[bool] = None

    @field_validator("tipo_lancamento")
    @classmethod
    def validar_tipo_lancamento(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if v not in ("D", "C"):
            raise ValueError("tipo_lancamento deve ser 'D' ou 'C'")
        return v

    @field_validator("modalidade")
    @classmethod
    def validar_modalidade(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if v not in MODALIDADES_VALIDAS:
            raise ValueError(f"modalidade deve ser uma de: {', '.join(MODALIDADES_VALIDAS)}")
        return v


class OperacaoFinanceiraResponse(OperacaoFinanceiraBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


OperacaoFinanceiraOut = OperacaoFinanceiraResponse
