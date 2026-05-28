"""add lancamento_padrao

Revision ID: 3da9a4a36094
Revises: g2h3i4j5k6l7
Create Date: 2026-05-28 08:14:15.827326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '3da9a4a36094'
down_revision: Union[str, Sequence[str], None] = 'g2h3i4j5k6l7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lancamento_padrao',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('lp_codigo', sa.String(length=10), nullable=False),
        sa.Column('descricao', sa.String(length=200), nullable=True),
        sa.Column('cfops', sa.JSON(), nullable=True),
        sa.Column('colunas_sft', sa.JSON(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'lp_codigo', name='uq_lp_empresa_codigo'),
        schema='concilia',
    )
    op.create_index('ix_concilia_lancamento_padrao_empresa_id', 'lancamento_padrao', ['empresa_id'], schema='concilia')


def downgrade() -> None:
    op.drop_index('ix_concilia_lancamento_padrao_empresa_id', table_name='lancamento_padrao', schema='concilia')
    op.drop_table('lancamento_padrao', schema='concilia')
