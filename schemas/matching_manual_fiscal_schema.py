"""
Schemas Pydantic para Matching Manual Fiscal.

Usado quando o matching automatico (tools/fiscal/match_ct2_sft.py) nao
consegue casar um lancamento CT2 com uma nota SFT sozinho -- tipicamente
porque o CT2_KEY veio vazio do Protheus e sobra mais de um fornecedor
candidato na mesma NF/filial/data -- e o usuario confirma manualmente a
correspondencia.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ItemMatchingManualIn(BaseModel):
    """Registro cru (CT2 ou SFT) selecionado pelo usuario para compor o match."""
    dados: Dict[str, Any]


class RequestCriarMatchingManual(BaseModel):
    empresa_id: int
    tipo: str  # "impostos" | "pre_conferencia"
    periodo: str  # "YYYY-MM"

    # Contexto -- Conciliacao de Impostos
    conta_contabil: Optional[str] = None
    campo_imposto: Optional[str] = None

    # Contexto -- Pre-Conferencia
    lp_codigo: Optional[str] = None
    lp_descricao: Optional[str] = None

    # Nome dos campos de valor em cada lado (impostos: campo_imposto/debito|credito;
    # pre-conferencia: _valor_calc/debito -- ver colunas_valor_sft do LP)
    campo_valor_sft: str = "valcont"
    campo_valor_ct2: str = "debito"

    itens_ct2: List[Dict[str, Any]]
    itens_sft: List[Dict[str, Any]]

    observacao: Optional[str] = None


class ItemMatchingManualOut(BaseModel):
    id: int
    lado: str
    historico: Optional[str] = None
    lote_sub_doc_linha: Optional[str] = None
    cfop: Optional[str] = None
    especie: Optional[str] = None
    data: Optional[str] = None
    valor: float
    dados_json: Dict[str, Any]

    class Config:
        from_attributes = True


class MatchingManualFiscalOut(BaseModel):
    id: int
    empresa_id: int
    tipo: str
    periodo: str
    conta_contabil: Optional[str] = None
    campo_imposto: Optional[str] = None
    lp_codigo: Optional[str] = None
    lp_descricao: Optional[str] = None
    filial: Optional[str] = None
    nf: Optional[str] = None
    cliefor: Optional[str] = None
    ct2_key: Optional[str] = None
    ct2_itemc: Optional[str] = None
    valor_total_ct2: float
    valor_total_sft: float
    observacao: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_nome: Optional[str] = None
    criado_em: datetime
    ativo: bool
    itens: List[ItemMatchingManualOut] = []

    class Config:
        from_attributes = True
