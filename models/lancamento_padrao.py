from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base


class LancamentoPadrao(Base):
    __tablename__ = "lancamento_padrao"
    __table_args__ = (
        UniqueConstraint("empresa_id", "lp_codigo", "descricao", name="uq_lp_empresa_codigo_desc"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    lp_codigo = Column(String(10), nullable=False)
    sequencia = Column(String(10))  # CT5_SEQUEN — distingue varios LPs com o mesmo lp_codigo
    descricao = Column(String(200), nullable=False, server_default="")
    grupo = Column(String(100))  # nome do grupo para agregação na pré-conferência
    cfops = Column(JSON)        # ["1101", "2101", "3101"]
    cfops_excluir = Column(JSON)        # CFOPs rejeitados na pre-conferencia
    tes_codes_excluir = Column(JSON)    # TES rejeitadas na pre-conferencia
    tes_codes = Column(JSON)    # ["001", "002"] — filtro de TES no SFT
    series = Column(JSON)       # ["1", "2"] — filtro de Serie da NF no SFT
    especies = Column(JSON)         # ["NFE", "CTE"] — filtro de Especie da NF no SFT
    especies_excluir = Column(JSON)     # Especies rejeitadas na pre-conferencia
    colunas_sft = Column(JSON)  # ["filial", "nf", "cliefor"]
    colunas_valor_sft = Column(JSON)  # ["difal", "vfcpdif"] — colunas somadas p/
                                       # "valor do SFT" na pre-conferencia;
                                       # null/vazio = usa valcont (padrao)
    ativo = Column(Boolean, default=True, nullable=False)
    excluido = Column(Boolean, default=False, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    empresa = relationship("Empresa")


class LancamentoPadraoCt2Layout(Base):
    """Mapeia, por empresa, qual familia de formula de CT2_KEY um LP usa --
    o Protheus grava a chave nativa (CT2_KEY) com layouts diferentes
    dependendo da origem do lancamento (estoque puro x compra x venda), e
    esse cadastro permite ao matching de conciliacao de estoque escolher a
    formula certa do lado do Kardex pra cada linha do Razao (ver ct2_lp)."""

    __tablename__ = "lancamento_padrao_ct2_layout"
    __table_args__ = (
        UniqueConstraint("empresa_id", "lp_codigo", name="uq_lp_ct2_layout_empresa_codigo"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    lp_codigo = Column(String(10), nullable=False)
    tipo_chave = Column(String(20), nullable=False)  # "ESTOQUE" | "COMPRA" | "VENDA"
    descricao = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    empresa = relationship("Empresa")
