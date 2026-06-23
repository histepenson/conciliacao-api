from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import date, datetime
from models.nfe import StatusNfe


class NfeItemEntradaOut(BaseModel):
    id: int
    numero_item: int
    codigo_produto_fornecedor: Optional[str] = None
    descricao_produto: Optional[str] = None
    ncm: Optional[str] = None
    cfop: Optional[str] = None
    unidade_comercial: Optional[str] = None
    quantidade: Optional[Decimal] = None
    valor_unitario: Optional[Decimal] = None
    valor_total_item: Optional[Decimal] = None
    produto_id: Optional[int] = None
    quantidade_convertida: Optional[Decimal] = None
    unidade_convertida: Optional[str] = None
    vinculo_pendente: bool

    model_config = {"from_attributes": True}


class NfeEntradaOut(BaseModel):
    id: int
    empresa_id: int
    chave_acesso: str
    numero_nf: Optional[str] = None
    serie: Optional[str] = None
    data_emissao: Optional[date] = None
    data_autorizacao: Optional[date] = None
    cnpj_emitente: str
    razao_social_emitente: Optional[str] = None
    valor_total: Optional[Decimal] = None
    status: StatusNfe
    created_at: datetime
    itens: list[NfeItemEntradaOut] = []

    model_config = {"from_attributes": True}


class NfeItemSaidaOut(BaseModel):
    id: int
    numero_item: int
    codigo_produto_empresa: Optional[str] = None
    descricao_produto: Optional[str] = None
    ncm: Optional[str] = None
    cfop: Optional[str] = None
    unidade_comercial: Optional[str] = None
    quantidade: Optional[Decimal] = None
    valor_unitario: Optional[Decimal] = None
    valor_total_item: Optional[Decimal] = None
    produto_id: Optional[int] = None
    quantidade_convertida: Optional[Decimal] = None
    unidade_convertida: Optional[str] = None
    vinculo_pendente: bool

    model_config = {"from_attributes": True}


class NfeSaidaOut(BaseModel):
    id: int
    empresa_id: int
    chave_acesso: str
    numero_nf: Optional[str] = None
    serie: Optional[str] = None
    data_emissao: Optional[date] = None
    data_autorizacao: Optional[date] = None
    cnpj_destinatario: Optional[str] = None
    razao_social_destinatario: Optional[str] = None
    valor_total: Optional[Decimal] = None
    status: StatusNfe
    created_at: datetime
    itens: list[NfeItemSaidaOut] = []

    model_config = {"from_attributes": True}


class NfeItemVinculoRequest(BaseModel):
    produto_id: int


class NfeImportarRequest(BaseModel):
    empresa_id: Optional[int] = None
    cnpj_certificado: str
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None


class TaskStatusOut(BaseModel):
    task_id: str
    status: str
    progresso: int
    total: int
    importadas: int
    pendentes_vinculo: int
    erro: Optional[str] = None
