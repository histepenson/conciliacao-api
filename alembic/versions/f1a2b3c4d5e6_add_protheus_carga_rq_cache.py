"""add protheus carga rq cache

Revision ID: f1a2b3c4d5e6
Revises: e4f5a6b7c8d9
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "protheus_carga_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("tipo_relatorio", sa.String(length=30), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("parametros_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("atualizar_automatico", sa.Boolean(), nullable=False),
        sa.Column("data_base_origem", sa.String(length=30), nullable=False),
        sa.Column("data_base_fixa", sa.String(length=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["concilia.empresa.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", "tipo_relatorio", "nome", name="uq_protheus_carga_config_empresa_relatorio_nome"),
        schema="concilia",
    )
    op.create_index(op.f("ix_concilia_protheus_carga_config_id"), "protheus_carga_config", ["id"], unique=False, schema="concilia")
    op.create_index(
        op.f("ix_concilia_protheus_carga_config_empresa_id"),
        "protheus_carga_config",
        ["empresa_id"],
        unique=False,
        schema="concilia",
    )
    op.create_index(
        op.f("ix_concilia_protheus_carga_config_tipo_relatorio"),
        "protheus_carga_config",
        ["tipo_relatorio"],
        unique=False,
        schema="concilia",
    )

    op.create_table(
        "protheus_carga",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("config_id", sa.Integer(), nullable=True),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("tipo_relatorio", sa.String(length=30), nullable=False),
        sa.Column("data_base", sa.String(length=8), nullable=False),
        sa.Column("parametros_hash", sa.String(length=64), nullable=False),
        sa.Column("parametros_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("total_registros", sa.Integer(), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("rq_job_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["config_id"], ["concilia.protheus_carga_config.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["empresa_id"], ["concilia.empresa.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "empresa_id",
            "tipo_relatorio",
            "data_base",
            "parametros_hash",
            name="uq_protheus_carga_empresa_relatorio_data_parametros",
        ),
        schema="concilia",
    )
    op.create_index(op.f("ix_concilia_protheus_carga_id"), "protheus_carga", ["id"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_protheus_carga_empresa_id"), "protheus_carga", ["empresa_id"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_protheus_carga_tipo_relatorio"), "protheus_carga", ["tipo_relatorio"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_protheus_carga_data_base"), "protheus_carga", ["data_base"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_protheus_carga_parametros_hash"), "protheus_carga", ["parametros_hash"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_protheus_carga_status"), "protheus_carga", ["status"], unique=False, schema="concilia")
    op.create_index(op.f("ix_concilia_protheus_carga_rq_job_id"), "protheus_carga", ["rq_job_id"], unique=False, schema="concilia")
    op.create_index("ix_protheus_carga_lookup", "protheus_carga", ["empresa_id", "tipo_relatorio", "data_base", "status"], schema="concilia")

    op.create_table(
        "protheus_carga_registro",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("carga_id", sa.Integer(), nullable=False),
        sa.Column("sequencia", sa.Integer(), nullable=False),
        sa.Column("dados_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["carga_id"], ["concilia.protheus_carga.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("carga_id", "sequencia", name="uq_protheus_carga_registro_carga_seq"),
        schema="concilia",
    )
    op.create_index(op.f("ix_concilia_protheus_carga_registro_id"), "protheus_carga_registro", ["id"], unique=False, schema="concilia")
    op.create_index("ix_protheus_carga_registro_carga", "protheus_carga_registro", ["carga_id"], unique=False, schema="concilia")


def downgrade() -> None:
    op.drop_index("ix_protheus_carga_registro_carga", table_name="protheus_carga_registro", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_registro_id"), table_name="protheus_carga_registro", schema="concilia")
    op.drop_table("protheus_carga_registro", schema="concilia")

    op.drop_index("ix_protheus_carga_lookup", table_name="protheus_carga", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_rq_job_id"), table_name="protheus_carga", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_status"), table_name="protheus_carga", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_parametros_hash"), table_name="protheus_carga", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_data_base"), table_name="protheus_carga", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_tipo_relatorio"), table_name="protheus_carga", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_empresa_id"), table_name="protheus_carga", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_id"), table_name="protheus_carga", schema="concilia")
    op.drop_table("protheus_carga", schema="concilia")

    op.drop_index(op.f("ix_concilia_protheus_carga_config_tipo_relatorio"), table_name="protheus_carga_config", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_config_empresa_id"), table_name="protheus_carga_config", schema="concilia")
    op.drop_index(op.f("ix_concilia_protheus_carga_config_id"), table_name="protheus_carga_config", schema="concilia")
    op.drop_table("protheus_carga_config", schema="concilia")
