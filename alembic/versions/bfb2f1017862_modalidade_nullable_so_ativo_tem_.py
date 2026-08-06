"""modalidade nullable so ativo tem modalidade

Revision ID: bfb2f1017862
Revises: d3e6f368680c
Create Date: 2026-08-06 18:20:28.117674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfb2f1017862'
down_revision: Union[str, Sequence[str], None] = 'd3e6f368680c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Solta o NOT NULL primeiro -- so' depois da coluna aceitar nulo e'
    # que da pra zerar a modalidade das naturezas inativas.
    op.alter_column(
        'operacao_financeira', 'modalidade',
        existing_type=sa.String(length=30),
        nullable=True,
        server_default=None,
        schema='concilia',
    )

    # Regra: modalidade so' pode estar preenchida quando ativo=true.
    op.execute("UPDATE concilia.operacao_financeira SET modalidade = NULL WHERE ativo = false")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE concilia.operacao_financeira SET modalidade = 'LEASING' WHERE modalidade IS NULL")
    op.alter_column(
        'operacao_financeira', 'modalidade',
        existing_type=sa.String(length=30),
        nullable=False,
        server_default='LEASING',
        schema='concilia',
    )
