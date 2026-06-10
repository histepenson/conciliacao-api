"""add ultimo_nsu to certificado_digital

Revision ID: 6f8ce258f645
Revises: 6ge9h0i1j2k3
Create Date: 2026-06-10 15:46:08.849759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f8ce258f645'
down_revision: Union[str, Sequence[str], None] = '6ge9h0i1j2k3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "certificado_digital",
        sa.Column("ultimo_nsu", sa.String(length=15), nullable=False, server_default="000000000000000"),
        schema="concilia",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("certificado_digital", "ultimo_nsu", schema="concilia")
