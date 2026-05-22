import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Enum, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class StatusCertificado(str, enum.Enum):
    valido = "valido"
    expirado = "expirado"
    invalido = "invalido"


class CertificadoDigital(Base):
    __tablename__ = "certificado_digital"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id"), nullable=False)
    cnpj_certificado = Column(String(14), nullable=False)
    razao_social_certificado = Column(String(255), nullable=True)
    caminho_arquivo = Column(String(500), nullable=False)
    senha_criptografada = Column(String(500), nullable=False)
    validade = Column(Date, nullable=True)
    status = Column(Enum(StatusCertificado, schema="concilia"), nullable=False, default=StatusCertificado.valido)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True)

    empresa = relationship("Empresa", foreign_keys=[empresa_id])

    def __repr__(self):
        return f"<CertificadoDigital(id={self.id}, cnpj='{self.cnpj_certificado}', status='{self.status}')>"
