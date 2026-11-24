@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo           INVENTIQ - SISTEMA WEB
echo ==========================================
python --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python no está instalado o no está agregado al PATH.
  echo Descarga Python 3.10+ desde https://www.python.org/downloads/
  pause
  exit /b 1
)
echo Instalando / verificando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo No se pudieron instalar las dependencias. Revisa tu conexion.
  pause
  exit /b 1
)
echo.
echo Iniciando INVENTIQ...
echo Abre en tu navegador: http://127.0.0.1:5000
start "INVENTIQ" http://127.0.0.1:5000
python webapp.py
pause
