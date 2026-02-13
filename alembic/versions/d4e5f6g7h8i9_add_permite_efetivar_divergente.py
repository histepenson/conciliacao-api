"""add permite_efetivar_divergente to empresa

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-02-13 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6g7h8i9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add permite_efetivar_divergente column to empresa table."""
    op.add_column(
        'empresa',
        sa.Column('permite_efetivar_divergente', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        schema='concilia'
    )


def downgrade() -> None:
    """Remove permite_efetivar_divergente column from empresa table."""
    op.drop_column('empresa', 'permite_efetivar_divergente', schema='concilia')
