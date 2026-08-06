# models/operacao_financeira.py
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db import Base


class OperacaoFinanceira(Base):
    """Cadastro de naturezas de lancamento (operacao financeira) por empresa.

    Cadastro generico (pode servir outras modalidades no futuro, nao so'
    leasing) -- por isso toda natureza carrega uma `modalidade`
    (ex: "LEASING"). Modulos como a Conferencia LEASING filtram por essa
    coluna pra so' enxergar as naturezas que pertencem a eles, mesmo que
    o cadastro cresca com naturezas de outras modalidades no mesmo
    empresa_id.

    Regra: modalidade so' pode estar preenchida quando `ativo=True`
    ("Considera=Sim"). Natureza inativa fica sempre com modalidade nula
    (nao pertence a nenhum modulo enquanto nao for reativada) -- aplicado
    em services/operacao_financeira_service.py.

    Usado hoje pela Conferencia LEASING (BBC) para classificar cada
    natureza importada dos relatorios (ex: N202, A300, ASSESS, LEILAO)
    com uma descricao e o tipo de lancamento (D/C) que ela representa na
    conferencia contra o razao contabil.
    """

    __tablename__ = "operacao_financeira"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", name="uq_operacao_financeira_empresa_codigo"),
        {"schema": "concilia"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    empresa_id = Column(Integer, ForeignKey("concilia.empresa.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo = Column(String(20), nullable=False)
    descricao = Column(String(200), nullable=False)
    tipo_lancamento = Column(String(1), nullable=False)  # "D" ou "C"
    modalidade = Column(String(30), nullable=True, index=True)
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    empresa = relationship("Empresa")
