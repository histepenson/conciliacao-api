# models/leasing_regra_classificacao.py
"""
Regra de classificacao do Extrato Bradesco por nome de cliente (usada
apenas pela Conferencia LEASING/BBC): o extrato bancario nao tem coluna
de natureza, entao a natureza de cada lancamento e' inferida comparando
"Cliente Debitado" contra o padrao cadastrado aqui (match tipo "contem",
case-insensitive). Ex: padrao_cliente="GARCIA PEREZ SOCIEDADE DE
ADVOGADOS" -> natureza_codigo="ASSESS"; padrao_cliente="LEIL" ->
natureza_codigo="LEILAO".

Tabela generica de cadastro (sem regra de negocio embutida aqui) -- quem
aplica o match e' o parser em services/estrategias/bbc/leasing_extrato_bradesco.py.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base


class LeasingRegraClassificacao(Base):
    __tablename__ = "leasing_regra_classificacao"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    padrao_cliente = Column(String(200), nullable=False)
    natureza_codigo = Column(String(20), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    empresa = relationship("Empresa")
