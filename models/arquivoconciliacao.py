from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base


class ArquivoConciliacao(Base):
    """Modelo de Arquivo de Conciliacao"""
    __tablename__ = "arquivos_conciliacao"
    __table_args__ = {"schema": "concilia"}


    # Colunas
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conciliacao_id = Column(Integer, ForeignKey("concilia.conciliacoes.id"), nullable=False, index=True)
    caminho_arquivo = Column(String(300), nullable=False)
    data_conciliacao = Column(DateTime, nullable=False)

    # Timestamps - padrao snake_case
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ============================================================
    # RELACIONAMENTOS
    # ============================================================

    # 1 arquivo -> 1 conciliacao
    conciliacao = relationship(
        "Conciliacao",
        back_populates="arquivo"
    )

    def __repr__(self):
        return f"<ArquivoConciliacao(id={self.id}, conciliacao_id={self.conciliacao_id})>"