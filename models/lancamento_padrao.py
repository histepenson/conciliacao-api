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
    descricao = Column(String(200), nullable=False, server_default="")
    cfops = Column(JSON)        # ["1101", "2101", "3101"]
    colunas_sft = Column(JSON)  # ["filial", "nf", "cliefor"]
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    empresa = relationship("Empresa")
