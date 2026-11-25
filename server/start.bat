@echo off
REM Arranca Jarvis en Windows. La primera vez crea el entorno e instala dependencias.
cd /d %~dp0
if not exist .venv (
  py -3.12 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python -m jarvis.main
pause
