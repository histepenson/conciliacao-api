from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base


class MatchingManualEstoque(Base):
    """
    Cabecalho de um matching manual entre movimentos do Kardex (MATR900) e
    lancamentos do Razao Contabil de Estoque (CTBR400) que o algoritmo
    automatico (tools/estoque/calc_diferencas_estoque.py) nao conseguiu
    casar sozinho.

    Um registro pode agrupar N movimentos de Kardex e M lancamentos de
    Razao (ver MatchingManualEstoqueItem) quando o movimento foi
    fracionado em varias linhas de cada lado.
    """
    __tablename__ = "matching_manual_estoque"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)

    periodo = Column(String(7), nullable=False)  # "YYYY-MM"
    conta_contabil = Column(String(20))
    conta_contabil_id = Column(Integer)
    codigo_movimento = Column(String(10))  # grupo de origem -- otimiza a busca na reaplicacao

    # Chave de negocio usada para reaplicar o match em cargas futuras --
    # nao ha campo unico compartilhado entre Kardex e Razao (diferente do
    # fiscal, onde filial+nf+cliefor serve pros dois lados), entao cada
    # lado tem sua propria chave.
    documento_numero = Column(String(30))  # kardex
    codigo_produto = Column(String(30))    # kardex
    armazem = Column(String(10))           # kardex
    data_kardex = Column(String(10))       # kardex
    historico = Column(String(200))        # razao
    data_razao = Column(String(10))        # razao

    valor_total_kardex = Column(Numeric(18, 2), nullable=False, default=0)
    valor_total_razao = Column(Numeric(18, 2), nullable=False, default=0)

    observacao = Column(Text)

    usuario_id = Column(Integer, ForeignKey("concilia.usuario.id", ondelete="SET NULL"))
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    desfeito_em = Column(DateTime(timezone=True))
    desfeito_por_id = Column(Integer, ForeignKey("concilia.usuario.id", ondelete="SET NULL"))

    empresa = relationship("Empresa")
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    desfeito_por = relationship("Usuario", foreign_keys=[desfeito_por_id])
    itens = relationship(
        "MatchingManualEstoqueItem", back_populates="matching", cascade="all, delete-orphan",
    )

    @property
    def ativo(self) -> bool:
        return self.desfeito_em is None

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None


class MatchingManualEstoqueItem(Base):
    """
    Um movimento de Kardex ou um lancamento de Razao especifico que compoe
    um matching manual. Guarda um snapshot dos dados no momento do match
    (o registro original em dados_json) para exibir na tela e auditar sem
    precisar rejuntar com a carga que pode ja ter sido reprocessada.
    """
    __tablename__ = "matching_manual_estoque_item"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    matching_manual_id = Column(
        Integer, ForeignKey("concilia.matching_manual_estoque.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    lado = Column(String(6), nullable=False)  # "kardex" | "razao"
    data = Column(String(10))
    documento_numero = Column(String(30))     # so kardex
    historico = Column(String(200))           # so razao
    valor = Column(Numeric(18, 2), nullable=False, default=0)
    dados_json = Column(JSONB, nullable=False)

    matching = relationship("MatchingManualEstoque", back_populates="itens")
