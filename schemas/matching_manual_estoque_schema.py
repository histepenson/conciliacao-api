"""
Schemas Pydantic para Matching Manual de Estoque.

Usado quando o matching automatico (tools/estoque/calc_diferencas_estoque.py)
nao consegue casar um movimento do Kardex (MATR900) com um lancamento do
Razao Contabil de Estoque (CTBR400) sozinho, e o usuario confirma
manualmente a correspondencia.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RequestCriarMatchingManualEstoque(BaseModel):
    empresa_id: int
    periodo: str  # "YYYY-MM"

    conta_contabil: Optional[str] = None
    conta_contabil_id: Optional[int] = None
    codigo_movimento: Optional[str] = None

    # Nome dos campos de valor em cada lado -- kardex sempre usa "valor";
    # razao usa "debito" ou "credito" conforme o grupo e' entrada ou saida.
    campo_valor_kardex: str = "valor"
    campo_valor_razao: str = "debito"

    itens_kardex: List[Dict[str, Any]]
    itens_razao: List[Dict[str, Any]]

    observacao: Optional[str] = None


class ItemMatchingManualEstoqueOut(BaseModel):
    id: int
    lado: str
    data: Optional[str] = None
    documento_numero: Optional[str] = None
    historico: Optional[str] = None
    valor: float
    dados_json: Dict[str, Any]

    class Config:
        from_attributes = True


class MatchingManualEstoqueOut(BaseModel):
    id: int
    empresa_id: int
    periodo: str
    conta_contabil: Optional[str] = None
    conta_contabil_id: Optional[int] = None
    codigo_movimento: Optional[str] = None
    documento_numero: Optional[str] = None
    codigo_produto: Optional[str] = None
    armazem: Optional[str] = None
    data_kardex: Optional[str] = None
    historico: Optional[str] = None
    data_razao: Optional[str] = None
    valor_total_kardex: float
    valor_total_razao: float
    observacao: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_nome: Optional[str] = None
    criado_em: datetime
    ativo: bool
    itens: List[ItemMatchingManualEstoqueOut] = []

    class Config:
        from_attributes = True
