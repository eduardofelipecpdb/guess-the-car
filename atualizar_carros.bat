@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo =========================================================
echo   Atualizando os 3 Carros do Dia (Shuffle Automatico)
echo =========================================================
python scripts\daily_shuffle.py %*
echo.
pause

