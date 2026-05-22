"""add efetivacao columns

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add efetivacao columns to conciliacoes table."""

    # Adicionar colunas de efetivacao na tabela conciliacoes
    op.add_column(
        'conciliacoes',
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PROCESSADA'),
        schema='concilia'
    )
    op.add_column(
        'conciliacoes',
        sa.Column('usuario_responsavel_id', sa.Integer(), nullable=True),
        schema='concilia'
    )
    op.add_column(
        'conciliacoes',
        sa.Column('data_efetivacao', sa.DateTime(timezone=True), nullable=True),
        schema='concilia'
    )
    op.add_column(
        'conciliacoes',
        sa.Column('resultado_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='concilia'
    )
    op.add_column(
        'conciliacoes',
        sa.Column('caminhos_arquivos', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='concilia'
    )

    # Criar indices
    op.create_index(
        'ix_conciliacoes_status',
        'conciliacoes',
        ['status'],
        unique=False,
        schema='concilia'
    )
    op.create_index(
        'ix_conciliacoes_usuario_responsavel',
        'conciliacoes',
        ['usuario_responsavel_id'],
        unique=False,
        schema='concilia'
    )
    op.create_index(
        'ix_conciliacoes_data_efetivacao',
        'conciliacoes',
        ['data_efetivacao'],
        unique=False,
        schema='concilia'
    )

    # Criar FK para usuario_responsavel
    op.create_foreign_key(
        'fk_conciliacoes_usuario_responsavel',
        'conciliacoes',
        'usuario',
        ['usuario_responsavel_id'],
        ['id'],
        source_schema='concilia',
        referent_schema='concilia',
        ondelete='SET NULL'
    )

    # Criar indice composto para busca de contas efetivadas por empresa/periodo
    op.create_index(
        'ix_conciliacoes_empresa_periodo_status',
        'conciliacoes',
        ['empresa_id', 'periodo', 'status'],
        unique=False,
        schema='concilia'
    )


def downgrade() -> None:
    """Downgrade schema - Remove efetivacao columns from conciliacoes table."""

    # Remover indice composto
    op.drop_index('ix_conciliacoes_empresa_periodo_status', table_name='conciliacoes', schema='concilia')

    # Remover FK
    op.drop_constraint('fk_conciliacoes_usuario_responsavel', 'conciliacoes', schema='concilia', type_='foreignkey')

    # Remover indices
    op.drop_index('ix_conciliacoes_data_efetivacao', table_name='conciliacoes', schema='concilia')
    op.drop_index('ix_conciliacoes_usuario_responsavel', table_name='conciliacoes', schema='concilia')
    op.drop_index('ix_conciliacoes_status', table_name='conciliacoes', schema='concilia')

    # Remover colunas
    op.drop_column('conciliacoes', 'caminhos_arquivos', schema='concilia')
    op.drop_column('conciliacoes', 'resultado_json', schema='concilia')
    op.drop_column('conciliacoes', 'data_efetivacao', schema='concilia')
    op.drop_column('conciliacoes', 'usuario_responsavel_id', schema='concilia')
    op.drop_column('conciliacoes', 'status', schema='concilia')
