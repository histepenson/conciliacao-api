"""add modalidade to operacao financeira

Revision ID: d3e6f368680c
Revises: fd769d615e6f
Create Date: 2026-08-06 18:08:04.987733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e6f368680c'
down_revision: Union[str, Sequence[str], None] = 'fd769d615e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'operacao_financeira',
        sa.Column('modalidade', sa.String(length=30), nullable=False, server_default='LEASING'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_operacao_financeira_modalidade'), 'operacao_financeira', ['modalidade'],
        unique=False, schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_concilia_operacao_financeira_modalidade'), table_name='operacao_financeira', schema='concilia')
    op.drop_column('operacao_financeira', 'modalidade', schema='concilia')
