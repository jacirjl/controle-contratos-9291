@echo off
chcp 65001 >nul
echo ======================================================================
echo  Utilitario de Reversao (Rollback) SDD / Git - Contrato 9291/2025
echo ======================================================================
echo.
cd /d "C:\ProgsAntigravity\Contratos"

echo [1] Tags de Marcos SDD (Spec-Driven Development) disponiveis:
git tag -n1
echo.
echo [2] Ultimos 10 Commits registrados no Historico:
git log -n 10 --oneline --decorate
echo.

set ALVO=%~1
if not "%ALVO%"=="" goto EXECUTAR_REVERSAO

echo Opcoes de Reversao:
echo  - Digite "ULTIMO" para reverter apenas o ultimo commit (git revert HEAD --no-edit)
echo  - Digite o nome de uma TAG SDD (ex: v1.2.1-sdd-spec03-fix-api) ou HASH de commit
echo    para restaurar todos os arquivos exatamente para aquele marco.
echo  - Pressione ENTER em branco para cancelar.
echo.
set /p ALVO="Informe o alvo da reversao (ULTIMO / Tag / Hash): "

if "%ALVO%"=="" (
    echo Operacao cancelada. Nenhuma alteracao foi feita.
    exit /b 0
)

:EXECUTAR_REVERSAO
if /I "%ALVO%"=="ULTIMO" (
    echo.
    echo Revertendo o ultimo commit de forma segura...
    git revert HEAD --no-edit
    git push origin main
    echo [OK] Ultima alteracao revertida e sincronizada no GitHub!
    exit /b 0
)

echo.
echo Restaurando estado do projeto para o marco [%ALVO%] (preservando historico)...
git checkout %ALVO% -- .
git commit -m "revert(sdd): restaura estado do sistema para o marco %ALVO%"
git push origin main
echo.
echo [OK] Sistema restaurado com sucesso para [%ALVO%] e sincronizado com o GitHub!
