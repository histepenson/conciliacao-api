#!/bin/bash

echo "🚀 Iniciando Sistema de Conciliação IA"
echo ""

# Cores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar se está no diretório correto
if [ ! -f "package.json" ]; then
    echo "❌ Erro: Execute este script dentro da pasta conciliacao-app/"
    exit 1
fi

# Verificar Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js não está instalado"
    echo "Instale em: https://nodejs.org"
    exit 1
fi

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python não está instalado"
    exit 1
fi

echo "✅ Node.js: $(node --version)"
echo "✅ Python: $(python3 --version)"
echo ""

# Verificar se dependências estão instaladas
if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependências do frontend..."
    npm install
fi

if [ ! -d "backend/venv" ]; then
    echo "📦 Criando ambiente virtual Python..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

echo ""
echo "${GREEN}========================================${NC}"
echo "${GREEN}🚀 Iniciando Aplicação...${NC}"
echo "${GREEN}========================================${NC}"
echo ""

# Iniciar backend em background
echo "${BLUE}[Backend]${NC} Iniciando API Python..."
cd backend
if [ -d "venv" ]; then
    source venv/bin/activate
fi
python3 main.py &
BACKEND_PID=$!
cd ..

# Aguardar backend iniciar
sleep 3

# Iniciar frontend
echo "${BLUE}[Frontend]${NC} Iniciando React..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "${GREEN}========================================${NC}"
echo "${GREEN}✅ Sistema Iniciado!${NC}"
echo "${GREEN}========================================${NC}"
echo ""
echo "${YELLOW}📍 URLs:${NC}"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "${YELLOW}⚠️  Para parar: Ctrl+C${NC}"
echo ""

# Aguardar Ctrl+C
trap "echo '' && echo 'Parando servidores...' && kill $BACKEND_PID $FRONTEND_PID 2>/dev/null && exit" INT

# Manter script rodando
wait
