@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Verificando carros do dia...
python scripts\daily_shuffle.py
echo.
echo Iniciando servidor local em http://localhost:8080 ...
start http://localhost:8080
python -m http.server 8080

