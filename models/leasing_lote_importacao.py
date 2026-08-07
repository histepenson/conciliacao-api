# models/leasing_lote_importacao.py
"""
Rastreio de cada upload feito na Conferencia LEASING (BBC): qual arquivo,
de qual tipo de relatorio, quando e quantas linhas geraram na
LeasingMovimentacao. Sem isso nao da pra saber a origem de uma linha nem
reprocessar/estornar uma importacao especifica.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base


class LeasingLoteImportacao(Base):
    __tablename__ = "leasing_lote_importacao"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo_relatorio = Column(String(30), nullable=False)  # CANCELAMENTO | CONTRATOS_2_6 | CONTRATOS_4 | BRADESCO | RAZAO
    nome_arquivo = Column(String(255), nullable=False)
    usuario_id = Column(Integer, ForeignKey("concilia.usuario.id"), nullable=True)
    qtd_linhas = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="concluido")  # concluido | erro
    erro_mensagem = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    empresa = relationship("Empresa")
