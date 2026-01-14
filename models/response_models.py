from pydantic import BaseModel
from typing import List

class DiferencaOrigemMaior(BaseModel):
    identificador: str
    data: str
    valor: float
    cliente_fornecedor: str
    descricao: str
    encontrado_lancamentos: bool
    conta_contabil_encontrada: str
    conta_contabil_esperada: str
    historico_lancamento: str
    data_lancamento: str
    criterio_match: str
    confianca_match: str
    situacao: str

class DiferencaContabilidadeMaior(BaseModel):
    identificador: str
    data: str
    valor: float
    conta_contabil: str
    historico: str
    existe_origem: bool
    verificacoes_realizadas: List[str]
    situacao: str

class ResumoConsolidacao(BaseModel):
    total_origem: float
    total_destino: float
    diferenca: float
    situacao: str
    percentual_divergencia: float
    quantidade_registros_origem: int
    quantidade_registros_destino: int
    data_processamento: str

class RelatorioConsolidacao(BaseModel):
    resumo: ResumoConsolidacao
    diferencas_origem_maior: List[DiferencaOrigemMaior]
    diferencas_contabilidade_maior: List[DiferencaContabilidadeMaior]
    observacoes: List[str]
    alertas: List[str]
