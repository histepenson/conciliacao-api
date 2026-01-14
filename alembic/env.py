from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# ============================================================
# ORDEM CORRETA: Primeiro importa os models, DEPOIS pega Base
# ============================================================

# 1. PRIMEIRO: Importa TODOS os models
from models import *

# 2. DEPOIS: Importa Base (agora com metadata populado)
from db import Base

# ============================================================

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Base.metadata agora tem todas as tabelas
target_metadata = Base.metadata


# ============================================================
# 🔒 FILTRO ABSOLUTO: SOMENTE schema = concilia
# ============================================================
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table":
        # ignora QUALQUER tabela fora do schema concilia
        return object.schema == "concilia"
    return True



def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_object=include_object,      # ✅ AQUI
        compare_type=True,
        compare_metadata=False,
        version_table_schema="concilia",
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=include_object,    # ✅ AQUI
            version_table_schema="concilia",
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


print("\n=== TABELAS NO METADATA ===")
for t in target_metadata.tables.values():
    print(f"{t.schema}.{t.name}")
