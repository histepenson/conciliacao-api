"""add balancete_conta

Revision ID: 429d84610342
Revises: 6f8ce258f645
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '429d84610342'
down_revision: Union[str, Sequence[str], None] = '6f8ce258f645'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'balancete_conta',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('conta_contabil_id', sa.Integer(), nullable=True),
        sa.Column('conta_codigo_raw', sa.String(length=50), nullable=False),
        sa.Column('conta_codigo_normalizado', sa.String(length=50), nullable=False),
        sa.Column('descricao', sa.String(length=255), nullable=True),
        sa.Column('periodo', sa.Date(), nullable=False),
        sa.Column('saldo_anterior', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('debito', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('credito', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('mov_periodo', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('saldo_atual', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id']),
        sa.ForeignKeyConstraint(['conta_contabil_id'], ['concilia.plano_contas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'conta_codigo_normalizado', 'periodo', name='uq_balancete_conta_periodo'),
        schema='concilia',
    )
    op.create_index(op.f('ix_concilia_balancete_conta_id'), 'balancete_conta', ['id'], unique=False, schema='concilia')
    op.create_index(op.f('ix_concilia_balancete_conta_empresa_id'), 'balancete_conta', ['empresa_id'], unique=False, schema='concilia')
    op.create_index(op.f('ix_concilia_balancete_conta_conta_contabil_id'), 'balancete_conta', ['conta_contabil_id'], unique=False, schema='concilia')
    op.create_index(op.f('ix_concilia_balancete_conta_conta_codigo_normalizado'), 'balancete_conta', ['conta_codigo_normalizado'], unique=False, schema='concilia')
    op.create_index(op.f('ix_concilia_balancete_conta_periodo'), 'balancete_conta', ['periodo'], unique=False, schema='concilia')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_concilia_balancete_conta_periodo'), table_name='balancete_conta', schema='concilia')
    op.drop_index(op.f('ix_concilia_balancete_conta_conta_codigo_normalizado'), table_name='balancete_conta', schema='concilia')
    op.drop_index(op.f('ix_concilia_balancete_conta_conta_contabil_id'), table_name='balancete_conta', schema='concilia')
    op.drop_index(op.f('ix_concilia_balancete_conta_empresa_id'), table_name='balancete_conta', schema='concilia')
    op.drop_index(op.f('ix_concilia_balancete_conta_id'), table_name='balancete_conta', schema='concilia')
    op.drop_table('balancete_conta', schema='concilia')
