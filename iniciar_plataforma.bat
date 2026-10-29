@echo off
echo ==============================================================
echo  Plataforma de Controle e Auditoria - Contrato 9291/2025
echo ==============================================================
echo.

cd /d "%~dp0"

echo Verificando porta 8092...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8092 " ^| findstr "LISTENING"') do (
    echo Encerrando instancia anterior na porta 8092 ^(PID %%a^)...
    taskkill /F /PID %%a >nul 2>&1
)

echo Abrindo navegador em http://localhost:8092/plataforma-controle-9291/index.html ...
start "" "http://localhost:8092/plataforma-controle-9291/index.html"

echo Iniciando servidor Python na porta 8092...
python server.py
