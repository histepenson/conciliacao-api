"""add dados_locais to empresa

Revision ID: 7a1b2c3d4e5f
Revises: 429d84610342
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '429d84610342'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'empresa',
        sa.Column('dados_locais', sa.Boolean(), server_default=sa.false(), nullable=False),
        schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('empresa', 'dados_locais', schema='concilia')
