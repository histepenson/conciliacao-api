"""add protheus connection fields to empresa

Revision ID: e4f5a6b7c8d9
Revises: c3e5f7a9b2d1
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'e4f5a6b7c8d9'
down_revision = 'c3e5f7a9b2d1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('empresa', sa.Column('protheus_url', sa.String(200), nullable=True), schema='concilia')
    op.add_column('empresa', sa.Column('protheus_rest_prefix', sa.String(50), nullable=True), schema='concilia')
    op.add_column('empresa', sa.Column('protheus_user', sa.String(100), nullable=True), schema='concilia')
    op.add_column('empresa', sa.Column('protheus_password', sa.Text(), nullable=True), schema='concilia')


def downgrade() -> None:
    op.drop_column('empresa', 'protheus_password', schema='concilia')
    op.drop_column('empresa', 'protheus_user', schema='concilia')
    op.drop_column('empresa', 'protheus_rest_prefix', schema='concilia')
    op.drop_column('empresa', 'protheus_url', schema='concilia')
