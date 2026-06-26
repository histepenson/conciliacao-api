"""add colunas_valor_sft to lancamento_padrao

Revision ID: k7l8m9n0o1p2
Revises: a4f6c8e0b3d5
Create Date: 2026-06-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "k7l8m9n0o1p2"
down_revision: Union[str, Sequence[str], None] = "a4f6c8e0b3d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lancamento_padrao", sa.Column("colunas_valor_sft", sa.JSON(), nullable=True), schema="concilia")


def downgrade() -> None:
    op.drop_column("lancamento_padrao", "colunas_valor_sft", schema="concilia")
