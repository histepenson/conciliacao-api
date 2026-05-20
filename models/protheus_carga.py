from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db import Base


class ProtheusCargaConfig(Base):
    __tablename__ = "protheus_carga_config"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "tipo_relatorio",
            "nome",
            name="uq_protheus_carga_config_empresa_relatorio_nome",
        ),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, index=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_relatorio = Column(String(30), nullable=False, index=True)
    nome = Column(String(150), nullable=False)
    parametros_json = Column(JSONB, nullable=False, default=dict)
    ativo = Column(Boolean, nullable=False, default=True)
    atualizar_automatico = Column(Boolean, nullable=False, default=True)
    data_base_origem = Column(String(30), nullable=False, default="periodo_aberto")
    data_base_fixa = Column(String(8), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    empresa = relationship("Empresa")
    cargas = relationship("ProtheusCarga", back_populates="config")


class ProtheusCarga(Base):
    __tablename__ = "protheus_carga"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "tipo_relatorio",
            "data_base",
            "parametros_hash",
            name="uq_protheus_carga_empresa_relatorio_data_parametros",
        ),
        Index("ix_protheus_carga_lookup", "empresa_id", "tipo_relatorio", "data_base", "status"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("concilia.protheus_carga_config.id", ondelete="SET NULL"), nullable=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_relatorio = Column(String(30), nullable=False, index=True)
    data_base = Column(String(8), nullable=False, index=True)
    parametros_hash = Column(String(64), nullable=False, index=True)
    parametros_json = Column(JSONB, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="pendente", index=True)
    total_registros = Column(Integer, nullable=False, default=0)
    iniciado_em = Column(DateTime(timezone=True), nullable=True)
    finalizado_em = Column(DateTime(timezone=True), nullable=True)
    erro = Column(Text, nullable=True)
    rq_job_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    config = relationship("ProtheusCargaConfig", back_populates="cargas")
    empresa = relationship("Empresa")
    registros = relationship("ProtheusCargaRegistro", back_populates="carga", cascade="all, delete-orphan")


class ProtheusCargaRegistro(Base):
    __tablename__ = "protheus_carga_registro"
    __table_args__ = (
        UniqueConstraint("carga_id", "sequencia", name="uq_protheus_carga_registro_carga_seq"),
        Index("ix_protheus_carga_registro_carga", "carga_id"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, index=True)
    carga_id = Column(Integer, ForeignKey("concilia.protheus_carga.id", ondelete="CASCADE"), nullable=False)
    sequencia = Column(Integer, nullable=False)
    dados_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    carga = relationship("ProtheusCarga", back_populates="registros")
