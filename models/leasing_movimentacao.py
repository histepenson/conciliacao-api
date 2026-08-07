# models/leasing_movimentacao.py
"""
Tabela unificada da Conferencia LEASING (BBC): uma linha por lancamento
(ou subtotal de natureza, ver services/estrategias/bbc/) vindo de
qualquer um dos relatorios de origem (Cancelamento, Contratos 2 e 6,
Contratos 4, Extrato Bradesco). E' a base que depois e' comparada contra
o razao contabil, agregada por natureza.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base


class LeasingMovimentacao(Base):
    __tablename__ = "leasing_movimentacao"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    lote_importacao_id = Column(
        Integer, ForeignKey("concilia.leasing_lote_importacao.id", ondelete="CASCADE"), nullable=False, index=True
    )

    arquivo_origem = Column(String(255), nullable=True)
    relatorio = Column(String(100), nullable=True)  # ex: "Apropriacao de receita", "Extrato Bradesco"
    lcto = Column(String(20), nullable=True)
    dt_lanc = Column(DateTime(timezone=True), nullable=True)
    nr_operacao = Column(String(30), nullable=True)
    cliente = Column(String(200), nullable=True)
    nr_parc = Column(String(20), nullable=True)
    dt_mov = Column(DateTime(timezone=True), nullable=True)

    natureza_codigo = Column(String(20), nullable=True, index=True)  # ex: N202, ASSESS -- nulo = nao classificado
    natureza_descricao = Column(String(200), nullable=True)
    conta_debito = Column(String(50), nullable=True)
    conta_credito = Column(String(50), nullable=True)

    valor = Column(Numeric(18, 2), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    empresa = relationship("Empresa")
    lote_importacao = relationship("LeasingLoteImportacao")
