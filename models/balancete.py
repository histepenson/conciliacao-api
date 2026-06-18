from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Numeric, text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class BalanceteConta(Base):
    """Snapshot do balancete contabil (importado) por conta e periodo."""
    __tablename__ = "balancete_conta"
    __table_args__ = (
        UniqueConstraint("empresa_id", "conta_codigo_normalizado", "periodo", name="uq_balancete_conta_periodo"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False, index=True)
    conta_contabil_id = Column(Integer, ForeignKey("concilia.plano_contas.id"), nullable=True, index=True)

    conta_codigo_raw = Column(String(50), nullable=False)
    conta_codigo_normalizado = Column(String(50), nullable=False, index=True)
    descricao = Column(String(255), nullable=True)

    periodo = Column(Date, nullable=False, index=True)  # primeiro dia do mes

    saldo_anterior = Column(Numeric(18, 2), nullable=False, default=0)
    debito = Column(Numeric(18, 2), nullable=False, default=0)
    credito = Column(Numeric(18, 2), nullable=False, default=0)
    mov_periodo = Column(Numeric(18, 2), nullable=False, default=0)
    saldo_atual = Column(Numeric(18, 2), nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
    conta_contabil = relationship("PlanoDeContas", foreign_keys=[conta_contabil_id])

    def __repr__(self):
        return f"<BalanceteConta(empresa_id={self.empresa_id}, conta='{self.conta_codigo_normalizado}', periodo={self.periodo})>"
