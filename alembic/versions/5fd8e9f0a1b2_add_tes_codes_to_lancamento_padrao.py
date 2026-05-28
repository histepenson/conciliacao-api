"""add tes_codes to lancamento_padrao

Revision ID: 5fd8e9f0a1b2
Revises: 4ec7d8f9a0b1
Create Date: 2026-05-28 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '5fd8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = '4ec7d8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'lancamento_padrao',
        sa.Column('tes_codes', sa.JSON(), nullable=True),
        schema='concilia',
    )


def downgrade() -> None:
    op.drop_column('lancamento_padrao', 'tes_codes', schema='concilia')
