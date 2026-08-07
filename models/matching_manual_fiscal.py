from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base


class MatchingManualFiscal(Base):
    """
    Cabecalho de um matching manual entre lancamentos CT2 (razao) e notas SFT
    que o algoritmo automatico (tools/fiscal/match_ct2_sft.py) nao conseguiu
    casar sozinho -- tipicamente quando o CT2_KEY vem vazio do Protheus e sobra
    mais de um fornecedor candidato na mesma NF/filial/data.

    Um registro pode agrupar N lancamentos CT2 e M notas SFT (ver
    MatchingManualFiscalItem) quando a nota foi fracionada em varias linhas de
    cada lado.
    """
    __tablename__ = "matching_manual_fiscal"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)

    # "impostos" | "pre_conferencia"
    tipo = Column(String(20), nullable=False)
    periodo = Column(String(7), nullable=False)  # "YYYY-MM"

    # Contexto -- Conciliacao de Impostos
    conta_contabil = Column(String(20))
    campo_imposto = Column(String(20))  # valpis, valicm, valcof, ...

    # Contexto -- Pre-Conferencia
    lp_codigo = Column(String(10))
    lp_descricao = Column(String(200))

    # Chave de negocio usada para reaplicar o match em cargas futuras
    filial = Column(String(10))
    nf = Column(String(20))
    cliefor = Column(String(20))

    # Chave construida no mesmo formato do CT2_KEY nativo do Protheus
    # (filial[0:4] + nf + ... + cliefor[16:22]) -- gravada para auditoria e
    # para eventualmente alimentar o matching automatico com o mesmo padrao
    # usado quando o Protheus preenche o campo.
    ct2_key = Column(String(80))
    ct2_itemc = Column(String(20))

    valor_total_ct2 = Column(Numeric(18, 2), nullable=False, default=0)
    valor_total_sft = Column(Numeric(18, 2), nullable=False, default=0)

    observacao = Column(Text)

    usuario_id = Column(Integer, ForeignKey("concilia.usuario.id", ondelete="SET NULL"))
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    desfeito_em = Column(DateTime(timezone=True))
    desfeito_por_id = Column(Integer, ForeignKey("concilia.usuario.id", ondelete="SET NULL"))

    empresa = relationship("Empresa")
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    desfeito_por = relationship("Usuario", foreign_keys=[desfeito_por_id])
    itens = relationship(
        "MatchingManualFiscalItem", back_populates="matching", cascade="all, delete-orphan",
    )

    @property
    def ativo(self) -> bool:
        return self.desfeito_em is None

    @property
    def usuario_nome(self) -> str | None:
        return self.usuario.nome if self.usuario else None


class MatchingManualFiscalItem(Base):
    """
    Um lancamento CT2 ou uma nota SFT especifica que compoe um matching
    manual. Guarda um snapshot dos dados no momento do match (o registro
    original em dados_json) para exibir na tela e auditar sem precisar
    rejuntar com a carga que pode ja ter sido recarregada.
    """
    __tablename__ = "matching_manual_fiscal_item"
    __table_args__ = {"schema": "concilia"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    matching_manual_id = Column(
        Integer, ForeignKey("concilia.matching_manual_fiscal.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    lado = Column(String(3), nullable=False)  # "ct2" | "sft"
    historico = Column(String(200))
    lote_sub_doc_linha = Column(String(60))
    cfop = Column(String(10))
    especie = Column(String(20))
    data = Column(String(10))
    valor = Column(Numeric(18, 2), nullable=False, default=0)
    dados_json = Column(JSONB, nullable=False)

    matching = relationship("MatchingManualFiscal", back_populates="itens")
