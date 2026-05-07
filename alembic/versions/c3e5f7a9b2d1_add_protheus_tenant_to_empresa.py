"""add protheus_tenant to empresa

Revision ID: c3e5f7a9b2d1
Revises: a9f3c2e1b4d7
Create Date: 2026-05-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3e5f7a9b2d1'
down_revision = 'a9f3c2e1b4d7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'empresa',
        sa.Column('protheus_tenant', sa.String(100), nullable=True),
        schema='concilia',
    )


def downgrade() -> None:
    op.drop_column('empresa', 'protheus_tenant', schema='concilia')
