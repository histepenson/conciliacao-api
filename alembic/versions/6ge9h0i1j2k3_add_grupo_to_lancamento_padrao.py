"""add grupo to lancamento_padrao

Revision ID: 6ge9h0i1j2k3
Revises: 5fd8e9f0a1b2
Create Date: 2026-05-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '6ge9h0i1j2k3'
down_revision: Union[str, Sequence[str], None] = '5fd8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'lancamento_padrao',
        sa.Column('grupo', sa.String(100), nullable=True),
        schema='concilia',
    )


def downgrade() -> None:
    op.drop_column('lancamento_padrao', 'grupo', schema='concilia')
