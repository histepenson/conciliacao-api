"""add sequencia to lancamento_padrao

Revision ID: 9c3d5e7f1a22
Revises: 8b2c4d6e8f10
Create Date: 2026-06-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "9c3d5e7f1a22"
down_revision: Union[str, Sequence[str], None] = "8b2c4d6e8f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lancamento_padrao", sa.Column("sequencia", sa.String(10), nullable=True), schema="concilia")


def downgrade() -> None:
    op.drop_column("lancamento_padrao", "sequencia", schema="concilia")
