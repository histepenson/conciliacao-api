import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Enum, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class OperacaoConversao(str, enum.Enum):
    multiplicar = "multiplicar"
    dividir = "dividir"


class ProdutoFornecedor(Base):
    __tablename__ = "produto_fornecedor"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    produto_id = Column(Integer, ForeignKey("concilia.produto.id"), nullable=False)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False)
    cnpj_fornecedor = Column(String(14), nullable=False)
    razao_social_fornecedor = Column(String(255), nullable=True)
    codigo_produto_fornecedor = Column(String(100), nullable=False)
    descricao_fornecedor = Column(String(255), nullable=True)
    unidade_compra = Column(String(20), nullable=False)
    fator_conversao = Column(Numeric(15, 4), nullable=False, default=1)
    operacao_conversao = Column(Enum(OperacaoConversao, schema="concilia"), nullable=False, default=OperacaoConversao.multiplicar)
    unidade_convertida = Column(String(20), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    produto = relationship("Produto", back_populates="fornecedores")
    empresa = relationship("Empresa", foreign_keys=[empresa_id])

    def __repr__(self):
        return f"<ProdutoFornecedor(id={self.id}, cnpj='{self.cnpj_fornecedor}', codigo='{self.codigo_produto_fornecedor}')>"
