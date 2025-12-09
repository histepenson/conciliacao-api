@echo off
echo ========================================
echo      Sistema de Conciliacao IA
echo ========================================
echo.

REM Verificar Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js nao esta instalado
    echo Instale em: https://nodejs.org
    pause
    exit /b 1
)

REM Verificar Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python nao esta instalado
    pause
    exit /b 1
)

echo [OK] Node.js: 
node --version
echo [OK] Python: 
python --version
echo.

REM Instalar dependencias se necessario
if not exist "node_modules" (
    echo [INFO] Instalando dependencias do frontend...
    call npm install
)

if not exist "backend\venv" (
    echo [INFO] Criando ambiente virtual Python...
    cd backend
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt
    cd ..
)

echo.
echo ========================================
echo  Iniciando Aplicacao...
echo ========================================
echo.

REM Iniciar backend
echo [Backend] Iniciando API Python...
cd backend
start /B python main.py
cd ..

REM Aguardar backend iniciar
timeout /t 3 /nobreak >nul

REM Iniciar frontend
echo [Frontend] Iniciando React...
start /B npm run dev

echo.
echo ========================================
echo  Sistema Iniciado!
echo ========================================
echo.
echo URLs:
echo    Frontend: http://localhost:3000
echo    Backend:  http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo.
echo Pressione Ctrl+C para parar
echo.

pause
