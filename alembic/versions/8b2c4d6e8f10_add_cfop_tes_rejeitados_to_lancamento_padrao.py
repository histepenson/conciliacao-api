"""add cfop tes rejeitados to lancamento_padrao

Revision ID: 8b2c4d6e8f10
Revises: 7a1b2c3d4e5f
Create Date: 2026-06-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "8b2c4d6e8f10"
down_revision: Union[str, Sequence[str], None] = "7a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lancamento_padrao", sa.Column("cfops_excluir", sa.JSON(), nullable=True), schema="concilia")
    op.add_column("lancamento_padrao", sa.Column("tes_codes_excluir", sa.JSON(), nullable=True), schema="concilia")


def downgrade() -> None:
    op.drop_column("lancamento_padrao", "tes_codes_excluir", schema="concilia")
    op.drop_column("lancamento_padrao", "cfops_excluir", schema="concilia")
