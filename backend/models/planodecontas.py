from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean,Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class PlanoDeContas(Base):
    """Modelo de Plano de Contas"""
    __tablename__ = "plano_contas"
    __table_args__ = (
        Index (
            "ix_plano_contas_empresa_conta",
            "empresa_id",
            "conta_contabil",
            unique=True
        ),
        {"schema": "concilia"}
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    empresa_id = Column(
        Integer,
        ForeignKey("concilia.empresa.id"),
        nullable=False,
        index=True
    )

    conta_contabil = Column(String(50), nullable=False, index=True)
    tipo_conta = Column(String(20), nullable=False)
    conciliavel = Column(Boolean, default=False, nullable=False)
    descricao = Column(String(255), nullable=True)

    # 🔹 SEM FK | apenas referência lógica (ex: "1", "1.01", "1.01.02")
    conta_superior = Column(String(50), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # ================= RELACIONAMENTOS =================

    empresa = relationship(
        "Empresa",
        back_populates="plano_contas"
    )

    conciliacoes = relationship(
        "Conciliacao",
        back_populates="conta_contabil",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self):
        return (
            f"<PlanoDeContas(id={self.id}, conta='{self.conta_contabil}', "
            f"tipo='{self.tipo_conta}')>"
        )
