"""add lancamento_padrao_ct2_layout

Revision ID: c42ca954c0f0
Revises: 23606bc38406
Create Date: 2026-09-07 17:11:54.696759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c42ca954c0f0'
down_revision: Union[str, Sequence[str], None] = '23606bc38406'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'lancamento_padrao_ct2_layout',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('lp_codigo', sa.String(length=10), nullable=False),
        sa.Column('tipo_chave', sa.String(length=20), nullable=False),
        sa.Column('descricao', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'lp_codigo', name='uq_lp_ct2_layout_empresa_codigo'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_lancamento_padrao_ct2_layout_empresa_id'),
        'lancamento_padrao_ct2_layout',
        ['empresa_id'],
        unique=False,
        schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_concilia_lancamento_padrao_ct2_layout_empresa_id'),
        table_name='lancamento_padrao_ct2_layout',
        schema='concilia',
    )
    op.drop_table('lancamento_padrao_ct2_layout', schema='concilia')
