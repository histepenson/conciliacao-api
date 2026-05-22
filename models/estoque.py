import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Date, Boolean, Enum, text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class TipoMovimentacao(str, enum.Enum):
    entrada = "entrada"
    saida = "saida"
    ajuste = "ajuste"
    estorno = "estorno"


class EstoqueSaldo(Base):
    __tablename__ = "estoque_saldo"
    __table_args__ = (
        UniqueConstraint("empresa_id", "produto_id", "periodo", name="uq_estoque_saldo_periodo"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("concilia.produto.id"), nullable=False)
    periodo = Column(Date, nullable=False)          # primeiro dia do mês: 2025-01-01
    saldo_inicial = Column(Numeric(15, 4), nullable=False, default=0)
    entradas = Column(Numeric(15, 4), nullable=False, default=0)
    saidas = Column(Numeric(15, 4), nullable=False, default=0)
    ajustes = Column(Numeric(15, 4), nullable=False, default=0)
    saldo_final = Column(Numeric(15, 4), nullable=False, default=0)
    fechado = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    produto = relationship("Produto", foreign_keys=[produto_id])


class EstoqueMovimentacao(Base):
    __tablename__ = "estoque_movimentacao"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("concilia.produto.id"), nullable=False)
    data_movimentacao = Column(Date, nullable=False)
    tipo = Column(Enum(TipoMovimentacao, schema="concilia"), nullable=False)
    quantidade = Column(Numeric(15, 4), nullable=False)
    documento_origem = Column(String(100), nullable=True)
    justificativa = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    produto = relationship("Produto", foreign_keys=[produto_id])
