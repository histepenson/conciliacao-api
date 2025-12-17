from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, DECIMAL, text 
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class Conciliacao(Base):
    """Modelo de Conciliação"""
    __tablename__ = "conciliacoes"
    __table_args__ = {"schema": "concilia"}


    # Colunas
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False, index=True)
    conta_contabil_id = Column(Integer, ForeignKey("concilia.plano_contas.id"), nullable=False, index=True)
    periodo = Column(String(20), nullable=False, index=True)  # Ex: "2025-01" ou "01/2025"
    saldo = Column(DECIMAL(18, 2), nullable=False, default=0)

    # Timestamps - padrão snake_case
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ============================================================
    # RELACIONAMENTOS
    # ============================================================

    # N conciliações → 1 empresa
    empresa = relationship(
        "Empresa",  # ← SINGULAR (corrigido)
        back_populates="conciliacoes"
    )

    # N conciliações → 1 conta contábil
    conta_contabil = relationship(
        "PlanoDeContas",
        back_populates="conciliacoes"
    )

    # 1 conciliação → 1 arquivo (opcional)
    arquivo = relationship(
        "ArquivoConciliacao",
        back_populates="conciliacao",
        uselist=False,  # Relacionamento 1:1
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Conciliacao(id={self.id}, empresa_id={self.empresa_id}, periodo='{self.periodo}')>"