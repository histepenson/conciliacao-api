"""add series to lancamento_padrao

Revision ID: m8n9o0p1q2r3
Revises: k7l8m9n0o1p2
Create Date: 2026-06-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "m8n9o0p1q2r3"
down_revision: Union[str, Sequence[str], None] = "k7l8m9n0o1p2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lancamento_padrao", sa.Column("series", sa.JSON(), nullable=True), schema="concilia")


def downgrade() -> None:
    op.drop_column("lancamento_padrao", "series", schema="concilia")
