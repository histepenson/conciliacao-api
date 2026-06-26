"""add especies to lancamento_padrao

Revision ID: a4f6c8e0b3d5
Revises: 9c3d5e7f1a22
Create Date: 2026-06-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a4f6c8e0b3d5"
down_revision: Union[str, Sequence[str], None] = "9c3d5e7f1a22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lancamento_padrao", sa.Column("especies", sa.JSON(), nullable=True), schema="concilia")
    op.add_column("lancamento_padrao", sa.Column("especies_excluir", sa.JSON(), nullable=True), schema="concilia")


def downgrade() -> None:
    op.drop_column("lancamento_padrao", "especies_excluir", schema="concilia")
    op.drop_column("lancamento_padrao", "especies", schema="concilia")
