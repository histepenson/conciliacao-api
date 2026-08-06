"""add leasing razao contabil

Revision ID: fd769d615e6f
Revises: da96d5fb4a72
Create Date: 2026-08-06 16:01:22.663782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd769d615e6f'
down_revision: Union[str, Sequence[str], None] = 'da96d5fb4a72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'leasing_razao_contabil',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('lote_importacao_id', sa.Integer(), nullable=False),
        sa.Column('dt_lanc_contabil', sa.DateTime(timezone=True), nullable=True),
        sa.Column('conta_contabil', sa.String(length=50), nullable=True),
        sa.Column('nome_conta_contabil', sa.String(length=200), nullable=True),
        sa.Column('historico_padrao', sa.String(length=200), nullable=True),
        sa.Column('historico', sa.String(length=500), nullable=True),
        sa.Column('conta_contra', sa.String(length=50), nullable=True),
        sa.Column('nome_conta_contra', sa.String(length=200), nullable=True),
        sa.Column('valor_debito', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('valor_credito', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lote_importacao_id'], ['concilia.leasing_lote_importacao.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_leasing_razao_contabil_empresa_id'), 'leasing_razao_contabil', ['empresa_id'],
        unique=False, schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_leasing_razao_contabil_lote_importacao_id'), 'leasing_razao_contabil', ['lote_importacao_id'],
        unique=False, schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_leasing_razao_contabil_historico_padrao'), 'leasing_razao_contabil', ['historico_padrao'],
        unique=False, schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_concilia_leasing_razao_contabil_historico_padrao'), table_name='leasing_razao_contabil', schema='concilia')
    op.drop_index(op.f('ix_concilia_leasing_razao_contabil_lote_importacao_id'), table_name='leasing_razao_contabil', schema='concilia')
    op.drop_index(op.f('ix_concilia_leasing_razao_contabil_empresa_id'), table_name='leasing_razao_contabil', schema='concilia')
    op.drop_table('leasing_razao_contabil', schema='concilia')
