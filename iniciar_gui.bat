@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Falta el entorno Python. Segui la instalacion de README-INTERFAZ.md.
    pause
    exit /b 1
)
set PYTHONDONTWRITEBYTECODE=1
".venv\Scripts\python.exe" gui.py
if errorlevel 1 pause
