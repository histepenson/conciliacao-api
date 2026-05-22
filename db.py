from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from pathlib import Path

# ============================================================
# CARREGAMENTO DO .env - MULTI-AMBIENTE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Detecta o ambiente: APP_ENV=develop | production (default)
APP_ENV = os.getenv("APP_ENV", "production")
env_file = f".env.{APP_ENV}" if APP_ENV != "production" else ".env"
env_path = BASE_DIR / env_file

# Fallback para .env se o arquivo especifico nao existir
if not env_path.exists():
    env_path = BASE_DIR / ".env"

load_dotenv(dotenv_path=env_path, override=True)

print(f"[INFO] Ambiente: {APP_ENV.upper()}")
print(f"[INFO] Procurando .env em: {env_path}")
print(f"[INFO] .env existe? {env_path.exists()}")

# Pega a DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

print(f"[INFO] DATABASE_URL carregada: {DATABASE_URL[:50] if DATABASE_URL else 'NONE'}...")

# Verifica se a variavel foi carregada
if not DATABASE_URL:
    print(f"\n[ERRO] DATABASE_URL nao encontrada!")
    print(f"[INFO] Verifique se existe o arquivo: {env_path}")
    print(f"[INFO] O arquivo .env deve conter: DATABASE_URL=postgresql://...")
    raise ValueError(
        f"A variavel DATABASE_URL nao esta definida.\n"
        f"Esperado em: {env_path}\n"
        f"Arquivo existe? {env_path.exists()}"
    )

print("[OK] DATABASE_URL carregada com sucesso!")

# ============================================================
# CONFIGURACAO DO SQLAlchemy
# ============================================================

# Cria o engine do banco
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verifica conexao antes de usar
    pool_size=10,        # Pool de conexoes
    max_overflow=20,     # Conexoes extras quando necessario
    echo=False           # Mude para True para ver queries SQL
)

# Cria a sessao
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos
Base = declarative_base()

# ============================================================
# DEPENDENCY INJECTION para FastAPI
# ============================================================

def get_db():
    """
    Cria uma sessao do banco de dados para cada requisicao.
    Fecha automaticamente apos o uso.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================
# FUNCAO AUXILIAR PARA TESTAR CONEXAO
# ============================================================

def test_connection():
    """Testa se a conexao com o banco esta funcionando"""
    try:
        with engine.connect() as connection:
            print("[OK] Conexao com o banco de dados OK!")
            return True
    except Exception as e:
        print(f"[ERRO] Erro ao conectar no banco: {e}")
        return False


if __name__ == "__main__":
    # Testa a conexao quando executar diretamente
    print("\n[TEST] Testando conexao com o banco...")
    test_connection()