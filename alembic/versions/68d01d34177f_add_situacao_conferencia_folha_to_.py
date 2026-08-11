"""add situacao_conferencia_folha to plano_contas

Revision ID: 68d01d34177f
Revises: ccd5e7ce29e4
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68d01d34177f'
down_revision: Union[str, Sequence[str], None] = 'ccd5e7ce29e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'plano_contas',
        sa.Column('situacao_conferencia_folha', sa.String(length=40), nullable=True),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_plano_contas_situacao_conferencia_folha'), 'plano_contas', ['situacao_conferencia_folha'],
        unique=False, schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_concilia_plano_contas_situacao_conferencia_folha'), table_name='plano_contas', schema='concilia')
    op.drop_column('plano_contas', 'situacao_conferencia_folha', schema='concilia')
