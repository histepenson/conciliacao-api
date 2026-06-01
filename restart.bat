@echo off
cd /d "%~dp0"
echo Parando backend (porta 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /f /pid %%a 2>nul
timeout /t 2 /nobreak >nul
echo Iniciando backend...
call .\venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
