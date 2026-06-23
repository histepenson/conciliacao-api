"""lp unique por codigo e descricao

Revision ID: 4ec7d8f9a0b1
Revises: 3da9a4a36094
Create Date: 2026-05-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '4ec7d8f9a0b1'
down_revision: Union[str, Sequence[str], None] = '3da9a4a36094'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Garante que descricao nunca seja NULL
    op.execute("UPDATE concilia.lancamento_padrao SET descricao = '' WHERE descricao IS NULL")
    op.alter_column('lancamento_padrao', 'descricao',
                    existing_type=sa.String(200),
                    nullable=False,
                    server_default='',
                    schema='concilia')

    # Troca o unique constraint
    op.drop_constraint('uq_lp_empresa_codigo', 'lancamento_padrao', schema='concilia')
    op.create_unique_constraint(
        'uq_lp_empresa_codigo_desc',
        'lancamento_padrao',
        ['empresa_id', 'lp_codigo', 'descricao'],
        schema='concilia',
    )


def downgrade() -> None:
    op.drop_constraint('uq_lp_empresa_codigo_desc', 'lancamento_padrao', schema='concilia')
    op.create_unique_constraint(
        'uq_lp_empresa_codigo',
        'lancamento_padrao',
        ['empresa_id', 'lp_codigo'],
        schema='concilia',
    )
    op.alter_column('lancamento_padrao', 'descricao',
                    existing_type=sa.String(200),
                    nullable=True,
                    server_default=None,
                    schema='concilia')
