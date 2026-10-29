@echo off
echo ==============================================================
echo  Backup Automatico Git / GitHub (SDD - Contrato 9291/2025)
echo ==============================================================
echo.
cd /d "C:\ProgsAntigravity\Contratos"

set MSG=%~1
if "%MSG%"=="" set MSG=chore(sdd): backup automatico - %date% %time%

git add .
git commit -m "%MSG%"
git push origin main --tags
echo.
echo [OK] Backup e sincronizacao com GitHub concluidos com sucesso!
