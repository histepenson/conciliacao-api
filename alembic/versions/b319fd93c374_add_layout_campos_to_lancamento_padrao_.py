"""add layout_campos to lancamento_padrao_ct2_layout

Revision ID: b319fd93c374
Revises: d1b6f0789d08
Create Date: 2026-09-08 23:18:25.428065

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b319fd93c374'
down_revision: Union[str, Sequence[str], None] = 'd1b6f0789d08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'lancamento_padrao_ct2_layout',
        sa.Column('layout_campos', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('lancamento_padrao_ct2_layout', 'layout_campos', schema='concilia')
