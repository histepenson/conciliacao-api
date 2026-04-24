from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, DECIMAL, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class Conciliacao(Base):
    """Modelo de Conciliacao"""
    __tablename__ = "conciliacoes"
    __table_args__ = {"schema": "concilia"}


    # Colunas
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False, index=True)
    conta_contabil_id = Column(Integer, ForeignKey("concilia.plano_contas.id"), nullable=False, index=True)
    periodo = Column(String(20), nullable=False, index=True)  # Ex: "2025-01" ou "01/2025"
    saldo = Column(DECIMAL(18, 2), nullable=False, default=0)

    # Colunas de Efetivacao
    status = Column(String(20), nullable=False, default="PROCESSADA", index=True)  # PROCESSADA, EFETIVADA
    tipo_conciliacao = Column(String(20), nullable=True, default="receber", index=True)  # receber, pagar, banco, estoque
    usuario_responsavel_id = Column(Integer, ForeignKey("concilia.usuario.id"), nullable=True, index=True)
    data_efetivacao = Column(DateTime(timezone=True), nullable=True)
    resultado_json = Column(JSONB, nullable=True)  # Resultado completo da conciliacao
    caminhos_arquivos = Column(JSONB, nullable=True)  # Paths dos arquivos salvos

    # Timestamps - padrao snake_case
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ============================================================
    # RELACIONAMENTOS
    # ============================================================

    # N conciliacoes -> 1 empresa
    empresa = relationship(
        "Empresa",  # <- SINGULAR (corrigido)
        back_populates="conciliacoes"
    )

    # N conciliacoes -> 1 conta contabil
    conta_contabil = relationship(
        "PlanoDeContas",
        back_populates="conciliacoes"
    )

    # 1 conciliacao -> 1 arquivo (opcional)
    arquivo = relationship(
        "ArquivoConciliacao",
        back_populates="conciliacao",
        uselist=False,  # Relacionamento 1:1
        cascade="all, delete-orphan"
    )

    # N conciliacoes -> 1 usuario responsavel (efetivacao)
    usuario_responsavel = relationship(
        "Usuario",
        foreign_keys=[usuario_responsavel_id]
    )

    def __repr__(self):
        return f"<Conciliacao(id={self.id}, empresa_id={self.empresa_id}, periodo='{self.periodo}')>"