from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class Produto(Base):
    __tablename__ = "produto"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False)
    codigo_interno = Column(String(50), nullable=False)
    descricao = Column(String(255), nullable=False)
    ncm = Column(String(8), nullable=True)
    unidade_estoque = Column(String(20), nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    fornecedores = relationship("ProdutoFornecedor", back_populates="produto", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Produto(id={self.id}, codigo='{self.codigo_interno}', descricao='{self.descricao}')>"
