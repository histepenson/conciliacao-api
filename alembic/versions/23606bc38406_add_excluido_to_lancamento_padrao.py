"""add excluido to lancamento_padrao

Revision ID: 23606bc38406
Revises: 68d01d34177f
Create Date: 2026-08-12 09:50:33.805277

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23606bc38406'
down_revision: Union[str, Sequence[str], None] = '68d01d34177f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'lancamento_padrao',
        sa.Column('excluido', sa.Boolean(), server_default='false', nullable=False),
        schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('lancamento_padrao', 'excluido', schema='concilia')
