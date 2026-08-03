# models/empresa_configuracao.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from db import Base


class EmpresaConfiguracao(Base):
    """Particularidades por empresa (feature flags/estrategias), chave-valor auditavel."""

    __tablename__ = "empresa_configuracao"
    __table_args__ = (
        UniqueConstraint("empresa_id", "chave", name="uq_empresa_configuracao_empresa_chave"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    chave = Column(String(100), nullable=False)
    valor = Column(JSONB, nullable=False, default=dict)

    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    criado_por = Column(Integer, ForeignKey("concilia.usuario.id"), nullable=True)
    atualizado_em = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    atualizado_por = Column(Integer, ForeignKey("concilia.usuario.id"), nullable=True)

    empresa = relationship("Empresa")

    def __repr__(self):
        return f"<EmpresaConfiguracao(empresa_id={self.empresa_id}, chave='{self.chave}')>"
