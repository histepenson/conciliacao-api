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
    colunas_sft = Column(JSON)  # ["filial", "nf", "cliefor"]
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    empresa = relationship("Empresa")
