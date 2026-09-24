"""add sequencias_credito_imposto to lancamento_padrao_ct2_layout

Revision ID: a9c4e7d21b35
Revises: 8778386507e2
Create Date: 2026-09-24 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a9c4e7d21b35'
down_revision: Union[str, Sequence[str], None] = '8778386507e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'lancamento_padrao_ct2_layout',
        sa.Column('sequencias_credito_imposto', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('lancamento_padrao_ct2_layout', 'sequencias_credito_imposto', schema='concilia')
