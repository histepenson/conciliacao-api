"""add matching manual estoque tables

Revision ID: 8778386507e2
Revises: b319fd93c374
Create Date: 2026-09-15 19:37:43.231277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8778386507e2'
down_revision: Union[str, Sequence[str], None] = 'b319fd93c374'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'matching_manual_estoque',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('periodo', sa.String(length=7), nullable=False),
        sa.Column('conta_contabil', sa.String(length=20), nullable=True),
        sa.Column('conta_contabil_id', sa.Integer(), nullable=True),
        sa.Column('codigo_movimento', sa.String(length=10), nullable=True),
        sa.Column('documento_numero', sa.String(length=30), nullable=True),
        sa.Column('codigo_produto', sa.String(length=30), nullable=True),
        sa.Column('armazem', sa.String(length=10), nullable=True),
        sa.Column('data_kardex', sa.String(length=10), nullable=True),
        sa.Column('historico', sa.String(length=200), nullable=True),
        sa.Column('data_razao', sa.String(length=10), nullable=True),
        sa.Column('valor_total_kardex', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('valor_total_razao', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
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
        op.f('ix_concilia_matching_manual_estoque_empresa_id'), 'matching_manual_estoque', ['empresa_id'],
        unique=False, schema='concilia',
    )
    op.create_index(
        'ix_matching_manual_estoque_lookup', 'matching_manual_estoque',
        ['empresa_id', 'periodo', 'conta_contabil', 'codigo_movimento'],
        unique=False, schema='concilia',
    )

    op.create_table(
        'matching_manual_estoque_item',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('matching_manual_id', sa.Integer(), nullable=False),
        sa.Column('lado', sa.String(length=6), nullable=False),
        sa.Column('data', sa.String(length=10), nullable=True),
        sa.Column('documento_numero', sa.String(length=30), nullable=True),
        sa.Column('historico', sa.String(length=200), nullable=True),
        sa.Column('valor', sa.Numeric(precision=18, scale=2), nullable=False, server_default='0'),
        sa.Column('dados_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['matching_manual_id'], ['concilia.matching_manual_estoque.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_matching_manual_estoque_item_matching_manual_id'), 'matching_manual_estoque_item',
        ['matching_manual_id'], unique=False, schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_concilia_matching_manual_estoque_item_matching_manual_id'),
        table_name='matching_manual_estoque_item', schema='concilia',
    )
    op.drop_table('matching_manual_estoque_item', schema='concilia')

    op.drop_index('ix_matching_manual_estoque_lookup', table_name='matching_manual_estoque', schema='concilia')
    op.drop_index(
        op.f('ix_concilia_matching_manual_estoque_empresa_id'), table_name='matching_manual_estoque', schema='concilia',
    )
    op.drop_table('matching_manual_estoque', schema='concilia')
