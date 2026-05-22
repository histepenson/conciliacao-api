"""add tipo_conciliacao column

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-02-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tipo_conciliacao column and populate existing records."""

    # Adicionar coluna
    op.add_column(
        'conciliacoes',
        sa.Column('tipo_conciliacao', sa.String(length=20), nullable=True, server_default='receber'),
        schema='concilia'
    )

    # Criar indice
    op.create_index(
        'ix_conciliacoes_tipo_conciliacao',
        'conciliacoes',
        ['tipo_conciliacao'],
        unique=False,
        schema='concilia'
    )

    # Migrar dados existentes: detectar tipo "banco" pela presenca de movimentos_por_dia no resultado_json
    op.execute("""
        UPDATE concilia.conciliacoes
        SET tipo_conciliacao = 'banco'
        WHERE resultado_json IS NOT NULL
          AND resultado_json ? 'movimentos_por_dia'
    """)

    # Demais registros ficam como "receber" (default)
    op.execute("""
        UPDATE concilia.conciliacoes
        SET tipo_conciliacao = 'receber'
        WHERE tipo_conciliacao IS NULL
           OR tipo_conciliacao = 'receber'
    """)


def downgrade() -> None:
    """Remove tipo_conciliacao column."""
    op.drop_index('ix_conciliacoes_tipo_conciliacao', table_name='conciliacoes', schema='concilia')
    op.drop_column('conciliacoes', 'tipo_conciliacao', schema='concilia')
