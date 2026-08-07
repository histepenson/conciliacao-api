"""add matching manual fiscal tables

Revision ID: ccd5e7ce29e4
Revises: bfb2f1017862
Create Date: 2026-08-07 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ccd5e7ce29e4'
down_revision: Union[str, Sequence[str], None] = 'bfb2f1017862'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'matching_manual_fiscal',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('periodo', sa.String(length=7), nullable=False),
        sa.Column('conta_contabil', sa.String(length=20), nullable=True),
        sa.Column('campo_imposto', sa.String(length=20), nullable=True),
        sa.Column('lp_codigo', sa.String(length=10), nullable=True),
        sa.Column('lp_descricao', sa.String(length=200), nullable=True),
        sa.Column('filial', sa.String(length=10), nullable=True),
        sa.Column('nf', sa.String(length=20), nullable=True),
        sa.Column('cliefor', sa.String(length=20), nullable=True),
        sa.Column('ct2_key', sa.String(length=80), nullable=True),
        sa.Column('ct2_itemc', sa.String(length=20), nullable=True),
        sa.Column('valor_total_ct2', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('valor_total_sft', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('desfeito_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('desfeito_por_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['concilia.usuario.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['desfeito_por_id'], ['concilia.usuario.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_matching_manual_fiscal_empresa_id'), 'matching_manual_fiscal', ['empresa_id'],
        unique=False, schema='concilia',
    )
    op.create_index(
        'ix_matching_manual_fiscal_lookup', 'matching_manual_fiscal',
        ['empresa_id', 'tipo', 'periodo', 'filial', 'nf', 'cliefor'],
        unique=False, schema='concilia',
    )

    op.create_table(
        'matching_manual_fiscal_item',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('matching_manual_id', sa.Integer(), nullable=False),
        sa.Column('lado', sa.String(length=3), nullable=False),
        sa.Column('historico', sa.String(length=200), nullable=True),
        sa.Column('lote_sub_doc_linha', sa.String(length=60), nullable=True),
        sa.Column('cfop', sa.String(length=10), nullable=True),
        sa.Column('especie', sa.String(length=20), nullable=True),
        sa.Column('data', sa.String(length=10), nullable=True),
        sa.Column('valor', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('dados_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['matching_manual_id'], ['concilia.matching_manual_fiscal.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_matching_manual_fiscal_item_matching_manual_id'), 'matching_manual_fiscal_item',
        ['matching_manual_id'], unique=False, schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_concilia_matching_manual_fiscal_item_matching_manual_id'),
        table_name='matching_manual_fiscal_item', schema='concilia',
    )
    op.drop_table('matching_manual_fiscal_item', schema='concilia')

    op.drop_index('ix_matching_manual_fiscal_lookup', table_name='matching_manual_fiscal', schema='concilia')
    op.drop_index(
        op.f('ix_concilia_matching_manual_fiscal_empresa_id'), table_name='matching_manual_fiscal', schema='concilia',
    )
    op.drop_table('matching_manual_fiscal', schema='concilia')
