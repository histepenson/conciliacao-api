# models/leasing_razao_contabil.py
"""
Linhas do razao contabil importadas para a Conferencia LEASING (BBC).
Layout bem diferente da LeasingMovimentacao (vem de outro sistema, plano
de contas + historico padrao + debito/credito separados), por isso fica
em tabela propria -- e' o lado "razao" comparado contra a base unificada
(LeasingMovimentacao) no motor de matching.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base


class LeasingRazaoContabil(Base):
    __tablename__ = "leasing_razao_contabil"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    lote_importacao_id = Column(
        Integer, ForeignKey("concilia.leasing_lote_importacao.id", ondelete="CASCADE"), nullable=False, index=True
    )

    dt_lanc_contabil = Column(DateTime(timezone=True), nullable=True)
    conta_contabil = Column(String(50), nullable=True)
    nome_conta_contabil = Column(String(200), nullable=True)
    historico_padrao = Column(String(200), nullable=True, index=True)
    historico = Column(String(500), nullable=True)
    conta_contra = Column(String(50), nullable=True)
    nome_conta_contra = Column(String(200), nullable=True)
    valor_debito = Column(Numeric(18, 2), nullable=True)
    valor_credito = Column(Numeric(18, 2), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    empresa = relationship("Empresa")
    lote_importacao = relationship("LeasingLoteImportacao")
