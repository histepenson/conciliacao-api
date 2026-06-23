"""add ct5_referencia e pre_conferencia_regra

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "g2h3i4j5k6l7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ct5_referencia
    # Armazena os lancamentos padrao (CT5) importados do Protheus.
    # Serve como referencia para saber como extrair a NF do CT2_KEY.
    # ------------------------------------------------------------------
    op.create_table(
        "ct5_referencia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("filial", sa.String(length=15), nullable=True),
        sa.Column("lp_codigo", sa.String(length=10), nullable=False),
        sa.Column("chave_busca", sa.Text(), nullable=True),
        sa.Column("ordem_busca", sa.String(length=5), nullable=True),
        sa.Column("descricao", sa.String(length=250), nullable=True),
        sa.Column("alias_arq", sa.String(length=10), nullable=True),
        sa.Column("campo_nf", sa.String(length=50), nullable=True),
        sa.Column("nf_posicao_ini", sa.Integer(), nullable=True),
        sa.Column("nf_tamanho", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["concilia.empresa.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", "lp_codigo", name="uq_ct5_referencia_empresa_lp"),
        schema="concilia",
    )
    op.create_index(op.f("ix_concilia_ct5_referencia_id"), "ct5_referencia", ["id"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_ct5_referencia_empresa_id"), "ct5_referencia", ["empresa_id"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_ct5_referencia_lp_codigo"), "ct5_referencia", ["lp_codigo"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_ct5_referencia_alias_arq"), "ct5_referencia", ["alias_arq"], unique=False, schema="concilia")

    # ------------------------------------------------------------------
    # pre_conferencia_regra
    # Define a regra de comparacao entre CT2 (razao) e SFT (livro fiscal)
    # para cada lancamento padrao de uma empresa.
    # ------------------------------------------------------------------
    op.create_table(
        "pre_conferencia_regra",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("ct5_codigo", sa.String(length=20), nullable=False),
        sa.Column("ct5_desc", sa.String(length=250), nullable=True),
        sa.Column("campo_sft", sa.String(length=50), nullable=False),
        sa.Column("cfop_prefixos", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conta_de", sa.String(length=30), nullable=True),
        sa.Column("conta_ate", sa.String(length=30), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["concilia.empresa.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", "ct5_codigo", name="uq_pre_conferencia_regra_empresa_ct5"),
        schema="concilia",
    )
    op.create_index(op.f("ix_concilia_pre_conferencia_regra_id"), "pre_conferencia_regra", ["id"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_pre_conferencia_regra_empresa_id"), "pre_conferencia_regra", ["empresa_id"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_pre_conferencia_regra_ct5_codigo"), "pre_conferencia_regra", ["ct5_codigo"], unique=False, schema="concilia")


def downgrade() -> None:
    op.drop_index(op.f("ix_concilia_pre_conferencia_regra_ct5_codigo"), table_name="pre_conferencia_regra", schema="concilia")
    op.drop_index(op.f("ix_concilia_pre_conferencia_regra_empresa_id"), table_name="pre_conferencia_regra", schema="concilia")
    op.drop_index(op.f("ix_concilia_pre_conferencia_regra_id"), table_name="pre_conferencia_regra", schema="concilia")
    op.drop_table("pre_conferencia_regra", schema="concilia")

    op.drop_index(op.f("ix_concilia_ct5_referencia_alias_arq"), table_name="ct5_referencia", schema="concilia")
    op.drop_index(op.f("ix_concilia_ct5_referencia_lp_codigo"), table_name="ct5_referencia", schema="concilia")
    op.drop_index(op.f("ix_concilia_ct5_referencia_empresa_id"), table_name="ct5_referencia", schema="concilia")
    op.drop_index(op.f("ix_concilia_ct5_referencia_id"), table_name="ct5_referencia", schema="concilia")
    op.drop_table("ct5_referencia", schema="concilia")
