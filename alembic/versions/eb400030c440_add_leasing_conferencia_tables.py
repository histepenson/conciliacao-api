"""add leasing conferencia tables

Revision ID: eb400030c440
Revises: 98c9a7b32e01
Create Date: 2026-08-06 15:33:40.802069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb400030c440'
down_revision: Union[str, Sequence[str], None] = '98c9a7b32e01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'operacao_financeira',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=20), nullable=False),
        sa.Column('descricao', sa.String(length=200), nullable=False),
        sa.Column('tipo_lancamento', sa.String(length=1), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('empresa_id', 'codigo', name='uq_operacao_financeira_empresa_codigo'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_operacao_financeira_empresa_id'), 'operacao_financeira', ['empresa_id'],
        unique=False, schema='concilia',
    )

    op.create_table(
        'leasing_lote_importacao',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('tipo_relatorio', sa.String(length=30), nullable=False),
        sa.Column('nome_arquivo', sa.String(length=255), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('qtd_linhas', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='concluido'),
        sa.Column('erro_mensagem', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['concilia.usuario.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_leasing_lote_importacao_empresa_id'), 'leasing_lote_importacao', ['empresa_id'],
        unique=False, schema='concilia',
    )

    op.create_table(
        'leasing_movimentacao',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('lote_importacao_id', sa.Integer(), nullable=False),
        sa.Column('arquivo_origem', sa.String(length=255), nullable=True),
        sa.Column('relatorio', sa.String(length=100), nullable=True),
        sa.Column('lcto', sa.String(length=20), nullable=True),
        sa.Column('dt_lanc', sa.DateTime(timezone=True), nullable=True),
        sa.Column('nr_operacao', sa.String(length=30), nullable=True),
        sa.Column('cliente', sa.String(length=200), nullable=True),
        sa.Column('nr_parc', sa.String(length=20), nullable=True),
        sa.Column('dt_mov', sa.DateTime(timezone=True), nullable=True),
        sa.Column('natureza_codigo', sa.String(length=20), nullable=True),
        sa.Column('natureza_descricao', sa.String(length=200), nullable=True),
        sa.Column('conta_debito', sa.String(length=50), nullable=True),
        sa.Column('conta_credito', sa.String(length=50), nullable=True),
        sa.Column('valor', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lote_importacao_id'], ['concilia.leasing_lote_importacao.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_leasing_movimentacao_empresa_id'), 'leasing_movimentacao', ['empresa_id'],
        unique=False, schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_leasing_movimentacao_lote_importacao_id'), 'leasing_movimentacao', ['lote_importacao_id'],
        unique=False, schema='concilia',
    )
    op.create_index(
        op.f('ix_concilia_leasing_movimentacao_natureza_codigo'), 'leasing_movimentacao', ['natureza_codigo'],
        unique=False, schema='concilia',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_concilia_leasing_movimentacao_natureza_codigo'), table_name='leasing_movimentacao', schema='concilia')
    op.drop_index(op.f('ix_concilia_leasing_movimentacao_lote_importacao_id'), table_name='leasing_movimentacao', schema='concilia')
    op.drop_index(op.f('ix_concilia_leasing_movimentacao_empresa_id'), table_name='leasing_movimentacao', schema='concilia')
    op.drop_table('leasing_movimentacao', schema='concilia')

    op.drop_index(op.f('ix_concilia_leasing_lote_importacao_empresa_id'), table_name='leasing_lote_importacao', schema='concilia')
    op.drop_table('leasing_lote_importacao', schema='concilia')

    op.drop_index(op.f('ix_concilia_operacao_financeira_empresa_id'), table_name='operacao_financeira', schema='concilia')
    op.drop_table('operacao_financeira', schema='concilia')
