import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Date, Boolean, Enum, text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class StatusNfe(str, enum.Enum):
    autorizada = "autorizada"
    cancelada = "cancelada"
    denegada = "denegada"


# ─────────────────────────────────────────
# NF-e ENTRADA
# ─────────────────────────────────────────

class NfeEntrada(Base):
    __tablename__ = "nfe_entrada"
    __table_args__ = (
        UniqueConstraint("empresa_id", "chave_acesso", name="uq_nfe_entrada_chave"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False)
    chave_acesso = Column(String(44), nullable=False)
    numero_nf = Column(String(20), nullable=True)
    serie = Column(String(5), nullable=True)
    data_emissao = Column(Date, nullable=True)
    data_autorizacao = Column(Date, nullable=True)
    cnpj_emitente = Column(String(14), nullable=False)
    razao_social_emitente = Column(String(255), nullable=True)
    valor_total = Column(Numeric(15, 2), nullable=True)
    status = Column(Enum(StatusNfe, schema="concilia"), nullable=False, default=StatusNfe.autorizada)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    itens = relationship("NfeEntradaItem", back_populates="nfe", cascade="all, delete-orphan")


class NfeEntradaItem(Base):
    __tablename__ = "nfe_entrada_item"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nfe_entrada_id = Column(Integer, ForeignKey("concilia.nfe_entrada.id", ondelete="CASCADE"), nullable=False)
    numero_item = Column(Integer, nullable=False)
    codigo_produto_fornecedor = Column(String(100), nullable=True)
    descricao_produto = Column(String(255), nullable=True)
    ncm = Column(String(8), nullable=True)
    cfop = Column(String(4), nullable=True)
    unidade_comercial = Column(String(20), nullable=True)
    quantidade = Column(Numeric(15, 4), nullable=True)
    valor_unitario = Column(Numeric(15, 4), nullable=True)
    valor_total_item = Column(Numeric(15, 2), nullable=True)
    produto_id = Column(Integer, ForeignKey("concilia.produto.id"), nullable=True)
    quantidade_convertida = Column(Numeric(15, 4), nullable=True)
    unidade_convertida = Column(String(20), nullable=True)
    vinculo_pendente = Column(Boolean, default=True, nullable=False)

    nfe = relationship("NfeEntrada", back_populates="itens")
    produto = relationship("Produto", foreign_keys=[produto_id])


# ─────────────────────────────────────────
# NF-e SAÍDA
# ─────────────────────────────────────────

class NfeSaida(Base):
    __tablename__ = "nfe_saida"
    __table_args__ = (
        UniqueConstraint("empresa_id", "chave_acesso", name="uq_nfe_saida_chave"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False)
    chave_acesso = Column(String(44), nullable=False)
    numero_nf = Column(String(20), nullable=True)
    serie = Column(String(5), nullable=True)
    data_emissao = Column(Date, nullable=True)
    data_autorizacao = Column(Date, nullable=True)
    cnpj_destinatario = Column(String(14), nullable=True)
    razao_social_destinatario = Column(String(255), nullable=True)
    valor_total = Column(Numeric(15, 2), nullable=True)
    status = Column(Enum(StatusNfe, schema="concilia"), nullable=False, default=StatusNfe.autorizada)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    itens = relationship("NfeSaidaItem", back_populates="nfe", cascade="all, delete-orphan")


class NfeSaidaItem(Base):
    __tablename__ = "nfe_saida_item"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nfe_saida_id = Column(Integer, ForeignKey("concilia.nfe_saida.id", ondelete="CASCADE"), nullable=False)
    numero_item = Column(Integer, nullable=False)
    codigo_produto_empresa = Column(String(100), nullable=True)
    descricao_produto = Column(String(255), nullable=True)
    ncm = Column(String(8), nullable=True)
    cfop = Column(String(4), nullable=True)
    unidade_comercial = Column(String(20), nullable=True)
    quantidade = Column(Numeric(15, 4), nullable=True)
    valor_unitario = Column(Numeric(15, 4), nullable=True)
    valor_total_item = Column(Numeric(15, 2), nullable=True)
    produto_id = Column(Integer, ForeignKey("concilia.produto.id"), nullable=True)
    quantidade_convertida = Column(Numeric(15, 4), nullable=True)
    unidade_convertida = Column(String(20), nullable=True)
    vinculo_pendente = Column(Boolean, default=True, nullable=False)

    nfe = relationship("NfeSaida", back_populates="itens")
    produto = relationship("Produto", foreign_keys=[produto_id])
