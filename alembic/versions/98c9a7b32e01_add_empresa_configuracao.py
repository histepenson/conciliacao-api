"""add empresa_configuracao

Revision ID: 98c9a7b32e01
Revises: m8n9o0p1q2r3
Create Date: 2026-07-27 17:29:43.191650

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '98c9a7b32e01'
down_revision: Union[str, Sequence[str], None] = 'm8n9o0p1q2r3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('empresa_configuracao',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('chave', sa.String(length=100), nullable=False),
    sa.Column('valor', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('criado_por', sa.Integer(), nullable=True),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_por', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['atualizado_por'], ['concilia.usuario.id'], ),
    sa.ForeignKeyConstraint(['criado_por'], ['concilia.usuario.id'], ),
    sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('empresa_id', 'chave', name='uq_empresa_configuracao_empresa_chave'),
    schema='concilia'
    )
    op.create_index(op.f('ix_concilia_empresa_configuracao_empresa_id'), 'empresa_configuracao', ['empresa_id'], unique=False, schema='concilia')
    op.create_index(op.f('ix_concilia_empresa_configuracao_id'), 'empresa_configuracao', ['id'], unique=False, schema='concilia')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_concilia_empresa_configuracao_id'), table_name='empresa_configuracao', schema='concilia')
    op.drop_index(op.f('ix_concilia_empresa_configuracao_empresa_id'), table_name='empresa_configuracao', schema='concilia')
    op.drop_table('empresa_configuracao', schema='concilia')
