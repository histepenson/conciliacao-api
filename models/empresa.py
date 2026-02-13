# models/empresa.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class Empresa(Base):
    """Modelo de Empresa - Nome SINGULAR"""

    __tablename__ = "empresa"
    __table_args__ = {"schema": "concilia"}

    # Colunas
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(150), nullable=False)
    cnpj = Column(String(20), nullable=False, unique=True, index=True)
    status = Column(Boolean, default=True, nullable=False)
    permite_efetivar_divergente = Column(Boolean, default=False, nullable=False)

    # Timestamps - padrão snake_case
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    # Auditoria
    created_by = Column(Integer, ForeignKey("concilia.usuario.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("concilia.usuario.id"), nullable=True)

    # ============================================================
    # RELACIONAMENTOS
    # ============================================================

    # 1 empresa → N planos de contas
    plano_contas = relationship(
        "PlanoDeContas",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # 1 empresa → N conciliações
    conciliacoes = relationship(
        "Conciliacao",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # 1 empresa → N usuários (via UsuarioEmpresa)
    usuarios = relationship(
        "UsuarioEmpresa",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Relacionamento com usuários de auditoria
    criador = relationship("Usuario", foreign_keys=[created_by])
    atualizador = relationship("Usuario", foreign_keys=[updated_by])

    def __repr__(self):
        return f"<Empresa(id={self.id}, nome='{self.nome}', cnpj='{self.cnpj}')>"
