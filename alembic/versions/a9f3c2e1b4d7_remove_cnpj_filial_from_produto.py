"""remove cnpj_filial from produto

Revision ID: a9f3c2e1b4d7
Revises: 57a8bb43b573
Create Date: 2026-04-27 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a9f3c2e1b4d7'
down_revision: Union[str, Sequence[str], None] = '57a8bb43b573'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('produto', 'cnpj_filial', schema='concilia')


def downgrade() -> None:
    op.add_column('produto', sa.Column('cnpj_filial', sa.String(length=14), nullable=True), schema='concilia')
