@echo off
REM Duplo clique pra rodar no Windows. Na primeira vez instala o que precisa.
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python main.py --abrir
pause
