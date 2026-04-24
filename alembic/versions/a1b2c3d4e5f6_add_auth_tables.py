"""add auth tables

Revision ID: a1b2c3d4e5f6
Revises: 5bfb489bd4b2
Create Date: 2026-01-29 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5bfb489bd4b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add authentication tables."""

    # Tabela de Usuarios
    op.create_table(
        'usuario',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('senha_hash', sa.String(length=255), nullable=False),
        sa.Column('nome', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia'
    )
    op.create_index('ix_usuario_email', 'usuario', ['email'], unique=True, schema='concilia')
    op.create_index('ix_usuario_is_active', 'usuario', ['is_active'], unique=False, schema='concilia')

    # Tabela de Perfis (Roles)
    op.create_table(
        'perfil',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nome', sa.String(length=100), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('permissoes', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia'
    )
    op.create_index('ix_perfil_nome', 'perfil', ['nome'], unique=True, schema='concilia')

    # Inserir perfis padrao do sistema
    op.execute("""
        INSERT INTO concilia.perfil (nome, descricao, permissoes, is_system) VALUES
        ('admin_empresa', 'Administrador da Empresa', '["*"]', true),
        ('analista', 'Analista de Conciliacao', '["conciliacao:read", "conciliacao:write", "arquivo:read", "arquivo:upload", "relatorio:read", "relatorio:export", "plano_contas:read"]', true),
        ('visualizador', 'Apenas Visualizacao', '["conciliacao:read", "relatorio:read", "plano_contas:read"]', true)
    """)

    # Tabela de Associacao Usuario-Empresa
    op.create_table(
        'usuario_empresa',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('perfil_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['concilia.usuario.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['perfil_id'], ['concilia.perfil.id']),
        sa.ForeignKeyConstraint(['created_by'], ['concilia.usuario.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('usuario_id', 'empresa_id', name='uq_usuario_empresa'),
        schema='concilia'
    )
    op.create_index('ix_usuario_empresa_usuario', 'usuario_empresa', ['usuario_id'], unique=False, schema='concilia')
    op.create_index('ix_usuario_empresa_empresa', 'usuario_empresa', ['empresa_id'], unique=False, schema='concilia')
    op.create_index('ix_usuario_empresa_active', 'usuario_empresa', ['is_active'], unique=False, schema='concilia')

    # Tabela de Reset de Senha
    op.create_table(
        'password_reset',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['concilia.usuario.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia'
    )
    op.create_index('ix_password_reset_token', 'password_reset', ['token_hash'], unique=False, schema='concilia')
    op.create_index('ix_password_reset_expires', 'password_reset', ['expires_at'], unique=False, schema='concilia')

    # Tabela de Sessoes
    op.create_table(
        'user_session',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['concilia.usuario.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia'
    )
    op.create_index('ix_session_token', 'user_session', ['token_hash'], unique=False, schema='concilia')
    op.create_index('ix_session_usuario', 'user_session', ['usuario_id'], unique=False, schema='concilia')

    # Tabela de Auditoria
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('old_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_values', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['usuario_id'], ['concilia.usuario.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['empresa_id'], ['concilia.empresa.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        schema='concilia'
    )
    op.create_index('ix_audit_usuario', 'audit_log', ['usuario_id'], unique=False, schema='concilia')
    op.create_index('ix_audit_empresa', 'audit_log', ['empresa_id'], unique=False, schema='concilia')
    op.create_index('ix_audit_action', 'audit_log', ['action'], unique=False, schema='concilia')
    op.create_index('ix_audit_created', 'audit_log', ['created_at'], unique=False, schema='concilia')

    # Adicionar colunas de auditoria nas tabelas existentes
    op.add_column('empresa', sa.Column('created_by', sa.Integer(), nullable=True), schema='concilia')
    op.add_column('empresa', sa.Column('updated_by', sa.Integer(), nullable=True), schema='concilia')
    op.create_foreign_key('fk_empresa_created_by', 'empresa', 'usuario', ['created_by'], ['id'], source_schema='concilia', referent_schema='concilia')
    op.create_foreign_key('fk_empresa_updated_by', 'empresa', 'usuario', ['updated_by'], ['id'], source_schema='concilia', referent_schema='concilia')

    op.add_column('plano_contas', sa.Column('created_by', sa.Integer(), nullable=True), schema='concilia')
    op.add_column('plano_contas', sa.Column('updated_by', sa.Integer(), nullable=True), schema='concilia')
    op.create_foreign_key('fk_plano_contas_created_by', 'plano_contas', 'usuario', ['created_by'], ['id'], source_schema='concilia', referent_schema='concilia')
    op.create_foreign_key('fk_plano_contas_updated_by', 'plano_contas', 'usuario', ['updated_by'], ['id'], source_schema='concilia', referent_schema='concilia')

    op.add_column('conciliacoes', sa.Column('created_by', sa.Integer(), nullable=True), schema='concilia')
    op.add_column('conciliacoes', sa.Column('updated_by', sa.Integer(), nullable=True), schema='concilia')
    op.create_foreign_key('fk_conciliacoes_created_by', 'conciliacoes', 'usuario', ['created_by'], ['id'], source_schema='concilia', referent_schema='concilia')
    op.create_foreign_key('fk_conciliacoes_updated_by', 'conciliacoes', 'usuario', ['updated_by'], ['id'], source_schema='concilia', referent_schema='concilia')

    op.add_column('arquivos_conciliacao', sa.Column('created_by', sa.Integer(), nullable=True), schema='concilia')
    op.add_column('arquivos_conciliacao', sa.Column('updated_by', sa.Integer(), nullable=True), schema='concilia')
    op.create_foreign_key('fk_arquivos_created_by', 'arquivos_conciliacao', 'usuario', ['created_by'], ['id'], source_schema='concilia', referent_schema='concilia')
    op.create_foreign_key('fk_arquivos_updated_by', 'arquivos_conciliacao', 'usuario', ['updated_by'], ['id'], source_schema='concilia', referent_schema='concilia')


def downgrade() -> None:
    """Downgrade schema - Remove authentication tables."""

    # Remover FKs de auditoria das tabelas existentes
    op.drop_constraint('fk_arquivos_updated_by', 'arquivos_conciliacao', schema='concilia', type_='foreignkey')
    op.drop_constraint('fk_arquivos_created_by', 'arquivos_conciliacao', schema='concilia', type_='foreignkey')
    op.drop_column('arquivos_conciliacao', 'updated_by', schema='concilia')
    op.drop_column('arquivos_conciliacao', 'created_by', schema='concilia')

    op.drop_constraint('fk_conciliacoes_updated_by', 'conciliacoes', schema='concilia', type_='foreignkey')
    op.drop_constraint('fk_conciliacoes_created_by', 'conciliacoes', schema='concilia', type_='foreignkey')
    op.drop_column('conciliacoes', 'updated_by', schema='concilia')
    op.drop_column('conciliacoes', 'created_by', schema='concilia')

    op.drop_constraint('fk_plano_contas_updated_by', 'plano_contas', schema='concilia', type_='foreignkey')
    op.drop_constraint('fk_plano_contas_created_by', 'plano_contas', schema='concilia', type_='foreignkey')
    op.drop_column('plano_contas', 'updated_by', schema='concilia')
    op.drop_column('plano_contas', 'created_by', schema='concilia')

    op.drop_constraint('fk_empresa_updated_by', 'empresa', schema='concilia', type_='foreignkey')
    op.drop_constraint('fk_empresa_created_by', 'empresa', schema='concilia', type_='foreignkey')
    op.drop_column('empresa', 'updated_by', schema='concilia')
    op.drop_column('empresa', 'created_by', schema='concilia')

    # Remover tabelas de auth
    op.drop_index('ix_audit_created', table_name='audit_log', schema='concilia')
    op.drop_index('ix_audit_action', table_name='audit_log', schema='concilia')
    op.drop_index('ix_audit_empresa', table_name='audit_log', schema='concilia')
    op.drop_index('ix_audit_usuario', table_name='audit_log', schema='concilia')
    op.drop_table('audit_log', schema='concilia')

    op.drop_index('ix_session_usuario', table_name='user_session', schema='concilia')
    op.drop_index('ix_session_token', table_name='user_session', schema='concilia')
    op.drop_table('user_session', schema='concilia')

    op.drop_index('ix_password_reset_expires', table_name='password_reset', schema='concilia')
    op.drop_index('ix_password_reset_token', table_name='password_reset', schema='concilia')
    op.drop_table('password_reset', schema='concilia')

    op.drop_index('ix_usuario_empresa_active', table_name='usuario_empresa', schema='concilia')
    op.drop_index('ix_usuario_empresa_empresa', table_name='usuario_empresa', schema='concilia')
    op.drop_index('ix_usuario_empresa_usuario', table_name='usuario_empresa', schema='concilia')
    op.drop_table('usuario_empresa', schema='concilia')

    op.drop_index('ix_perfil_nome', table_name='perfil', schema='concilia')
    op.drop_table('perfil', schema='concilia')

    op.drop_index('ix_usuario_is_active', table_name='usuario', schema='concilia')
    op.drop_index('ix_usuario_email', table_name='usuario', schema='concilia')
    op.drop_table('usuario', schema='concilia')
