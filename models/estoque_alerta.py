import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Enum, text
from sqlalchemy.orm import relationship
from db import Base


class TipoAlerta(str, enum.Enum):
    sem_depara = "sem_depara"
    estoque_negativo = "estoque_negativo"
    periodo_reaberto = "periodo_reaberto"


class EstoqueAlerta(Base):
    __tablename__ = "estoque_alerta"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False)
    tipo = Column(Enum(TipoAlerta, schema="concilia"), nullable=False)
    referencia_id = Column(Integer, nullable=True)
    mensagem = Column(String(500), nullable=False)
    resolvido = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])
