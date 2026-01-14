from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from pathlib import Path

# ============================================================
# CARREGAMENTO DO .env - CORRIGIDO
# ============================================================

# Obtém o diretório do arquivo atual (backend/)
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
Base = declarative_base()

# Carrega o .env da pasta backend
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

print(f"🔍 Procurando .env em: {env_path}")
print(f"📁 .env existe? {env_path.exists()}")

# Pega a DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

print(f"🔗 DATABASE_URL carregada: {DATABASE_URL[:50] if DATABASE_URL else 'NONE'}...")

# Verifica se a variável foi carregada
if not DATABASE_URL:
    print(f"\n❌ ERRO: DATABASE_URL não encontrada!")
    print(f"📂 Verifique se existe o arquivo: {env_path}")
    print(f"💡 O arquivo .env deve conter: DATABASE_URL=postgresql://...")
    raise ValueError(
        f"A variável DATABASE_URL não está definida.\n"
        f"Esperado em: {env_path}\n"
        f"Arquivo existe? {env_path.exists()}"
    )

print("✅ DATABASE_URL carregada com sucesso!")

# ============================================================
# CONFIGURAÇÃO DO SQLAlchemy
# ============================================================

# Cria o engine do banco
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verifica conexão antes de usar
    pool_size=10,        # Pool de conexões
    max_overflow=20,     # Conexões extras quando necessário
    echo=False           # Mude para True para ver queries SQL
)

# Cria a sessão
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos
Base = declarative_base()

# ============================================================
# DEPENDENCY INJECTION para FastAPI
# ============================================================

def get_db():
    """
    Cria uma sessão do banco de dados para cada requisição.
    Fecha automaticamente após o uso.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================
# FUNÇÃO AUXILIAR PARA TESTAR CONEXÃO
# ============================================================

def test_connection():
    """Testa se a conexão com o banco está funcionando"""
    try:
        with engine.connect() as connection:
            print("✅ Conexão com o banco de dados OK!")
            return True
    except Exception as e:
        print(f"❌ Erro ao conectar no banco: {e}")
        return False


if __name__ == "__main__":
    # Testa a conexão quando executar diretamente
    print("\n🧪 Testando conexão com o banco...")
    test_connection()