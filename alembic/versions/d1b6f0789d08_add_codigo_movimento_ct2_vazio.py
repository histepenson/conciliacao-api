"""add codigo_movimento_ct2_vazio to lancamento_padrao_ct2_layout

Revision ID: d1b6f0789d08
Revises: c42ca954c0f0
Create Date: 2026-09-08 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd1b6f0789d08'
down_revision: Union[str, Sequence[str], None] = 'c42ca954c0f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'lancamento_padrao_ct2_layout',
        'tipo_chave',
        existing_type=sa.String(length=20),
        nullable=True,
        schema='concilia',
    )
    op.add_column(
        'lancamento_padrao_ct2_layout',
        sa.Column('codigo_movimento_ct2_vazio', sa.String(length=20), nullable=True),
        schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('lancamento_padrao_ct2_layout', 'codigo_movimento_ct2_vazio', schema='concilia')
    op.alter_column(
        'lancamento_padrao_ct2_layout',
        'tipo_chave',
        existing_type=sa.String(length=20),
        nullable=False,
        schema='concilia',
    )
