"""add leasing regra classificacao

Revision ID: da96d5fb4a72
Revises: eb400030c440
Create Date: 2026-08-06 15:55:22.999653

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da96d5fb4a72'
down_revision: Union[str, Sequence[str], None] = 'eb400030c440'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'leasing_regra_classificacao',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('padrao_cliente', sa.String(length=200), nullable=False),
        sa.Column('natureza_codigo', sa.String(length=20), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_leasing_regra_classificacao_empresa_id'), 'leasing_regra_classificacao', ['empresa_id'],
        unique=False, schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_concilia_leasing_regra_classificacao_empresa_id'), table_name='leasing_regra_classificacao', schema='concilia')
    op.drop_table('leasing_regra_classificacao', schema='concilia')
