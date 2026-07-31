from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

# =======================
# ENTRADA
# =======================

class BaseOrigem(BaseModel):
    registros: List[Dict[str, Any]]
    tipo: Optional[str] = None  # "contas_receber" ou "contas_pagar"


class Ctbr140Params(BaseModel):
    """
    Parametros para buscar o balancete CTBR140 diretamente do Protheus.
    Quando presente em BaseContabilFiltrada, o backend busca os dados
    automaticamente via ZCTBR140API -- nao e necessario enviar 'registros'.
    """
    data_fim: str                              # YYYYMMDD -- obrigatorio
    data_ini: Optional[str] = None            # YYYYMMDD -- default: 01/01 do ano de data_fim
    conta_de: Optional[str] = None
    conta_ate: Optional[str] = None
    item_de: Optional[str] = None
    item_ate: Optional[str] = None
    vlr_zerado: Optional[str] = None          # 1=inclui zeros  2=exclui
    moeda: Optional[str] = None               # default: 1
    tp_lanc: Optional[str] = None             # tipo de lancamento (vazio = todos)
    sld_ant_lp: Optional[str] = None          # 1=usa data_lp  2=usa data_ini-1
    data_lp: Optional[str] = None             # YYYYMMDD -- data base LP
    consid_filiais: Optional[str] = None      # 1=range  2=filial corrente
    filial_de: Optional[str] = None
    filial_ate: Optional[str] = None
    protheus_url: Optional[str] = None        # sobrescreve PROTHEUS_URL do .env


class BaseContabilFiltrada(BaseModel):
    # registros pode vir vazio quando ctbr140_params estiver preenchido
    registros: List[Dict[str, Any]] = Field(default_factory=list)
    conta_contabil: str
    ctbr140_params: Optional[Ctbr140Params] = None  # busca automatica via Protheus


class Ctbr480Params(BaseModel):
    """
    Parametros para buscar o razao contabil CTBR480 diretamente do Protheus.
    Quando presente em BaseContabilGeral, o backend busca os dados
    automaticamente via ZCTBR480API -- nao e necessario enviar 'registros'.
    """
    data_fim: str                              # YYYYMMDD -- obrigatorio
    data_ini: Optional[str] = None            # YYYYMMDD -- default: 01/01 do ano de data_fim
    item_de: Optional[str] = None             # CTD_ITEM inicio   (par01)
    item_ate: Optional[str] = None            # CTD_ITEM fim       (par02)
    conta_de: Optional[str] = None            # CT1_CONTA inicio  (par12)
    conta_ate: Optional[str] = None           # CT1_CONTA fim      (par13)
    custo_de: Optional[str] = None            # CTT_CUSTO inicio  (par15)
    custo_ate: Optional[str] = None           # CTT_CUSTO fim      (par16)
    clvl_de: Optional[str] = None             # CTH_CLVL inicio   (par18)
    clvl_ate: Optional[str] = None            # CTH_CLVL fim       (par19)
    moeda: Optional[str] = None               # default: 1         (par05)
    saldo: Optional[str] = None               # CQ5_TPSALD default: "1" (par06)
    vlr_zerado: Optional[str] = None          # 1=inclui zeros 2=exclui (par27)
    consid_filiais: Optional[str] = None      # 1=range 2=filial corrente (par29)
    filial_de: Optional[str] = None
    filial_ate: Optional[str] = None
    protheus_url: Optional[str] = None        # sobrescreve PROTHEUS_URL do .env


class BaseContabilGeral(BaseModel):
    # registros pode vir vazio quando ctbr480_params estiver preenchido
    registros: List[Dict[str, Any]] = Field(default_factory=list)
    ctbr480_params: Optional[Ctbr480Params] = None  # busca automatica via Protheus


class BaseCroms051(BaseModel):
    """
    Conta Corrente Desconto (CROMS051) - particularidade exclusiva da
    Rancheiro. Quando presente, o valor abate o saldo financeiro antes do
    calculo de diferencas (ver services/estrategias/abate_croms051.py).

    Duas formas de fornecer os dados:
    - carga_id: referencia a uma carga CROMS051 ja concluida (protheus_carga) --
      o backend le e agrega os registros direto do banco, sem o frontend
      precisar baixar/reenviar centenas de milhares de linhas.
    - registros: lista ja pronta (bruta ou agregada por cliente), para uso
      manual/legado.
    """
    carga_id: Optional[int] = None
    registros: List[Dict[str, Any]] = Field(default_factory=list)


class RequestConciliacao(BaseModel):
    base_origem: BaseOrigem
    base_contabil_filtrada: BaseContabilFiltrada
    base_contabil_geral: BaseContabilGeral
    base_croms051: Optional[BaseCroms051] = None
    parametros: Optional[Dict[str, Any]] = Field(default_factory=dict)


# =======================
# SAIDA
# =======================

class DiferencaOrigemMaior(BaseModel):
    identificador: str
    data: str
    valor: float
    cliente_fornecedor: str
    descricao: str
    encontrado_lancamentos: bool = False
    conta_contabil_encontrada: str = ""
    conta_contabil_esperada: str = ""
    historico_lancamento: str = ""
    data_lancamento: str = ""
    criterio_match: str = ""
    confianca_match: str = ""
    situacao: str = ""


class DiferencaContabilidadeMaior(BaseModel):
    identificador: str
    data: str
    valor: float
    conta_contabil: str
    historico: str
    existe_origem: bool = False
    verificacoes_realizadas: List[str] = []
    situacao: str = ""


class OrigemLancamento(BaseModel):
    """Representa uma origem identificada no razao geral para um lancamento SO_CONTABILIDADE."""
    conta_origem: str
    descricao_conta: str = ""
    valor: float
    tipo_lancamento: str = ""  # DEBITO | CREDITO
    data_lancamento: str = ""
    documento: str = ""
    historico: str = ""
    tipo_movimento: str  # TRANSFERENCIA | ALOCACAO | RECLASSIFICACAO | LANCAMENTO_AUTOMATICO | NAO_IDENTIFICADO
    ct5_desc: str = ""  # Descricao do lancamento padrao (CT5), presente quando origem e ZCT2RAZCT5


class AnaliseContabilProfunda(BaseModel):
    """Analise detalhada de um registro SO_CONTABILIDADE com busca no razao geral."""
    codigo: str
    nome: str
    valor_contabilidade: float
    conta_analisada: str
    origens_identificadas: List[OrigemLancamento] = []
    total_origens: int = 0
    status_analise: str  # ORIGEM_IDENTIFICADA | ORIGEM_NAO_IDENTIFICADA | MULTIPLAS_ORIGENS
    nota_explicativa: str = ""


class AnaliseDiferencaDetalhada(BaseModel):
    codigo: str
    nome: str
    conta_contabil: str
    valor_financeiro: float
    valor_contabilidade: float
    diferenca: float
    tipo_diferenca: str
    status: str
    lancamentos_razao: int = 0
    lancamentos_razao_detalhes: List[OrigemLancamento] = []
    lancamentos_financeiro_detalhes: List[OrigemLancamento] = []
    sem_lancamentos_razao: bool = False
    nota_razao: str = ""


class ResumoAnaliseDetalhada(BaseModel):
    total_registros: int
    conciliados: int
    divergentes: int
    percentual_conciliacao: float


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
    analise_detalhada: List[AnaliseDiferencaDetalhada] = []
    resumo_analise: Optional[ResumoAnaliseDetalhada] = None
    analise_profunda_contabil: List[AnaliseContabilProfunda] = []
    analise_movimentos_mes: Optional[Dict[str, Any]] = None
    observacoes: List[str] = []
    alertas: List[str] = []
