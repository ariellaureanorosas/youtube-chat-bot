@echo off
REM ============================================
REM  INICIAR BOT DO YOUTUBE LIVE CHAT
REM  Modo: GUI Unificada (manual ou OBS conforme config.yaml)
REM ============================================
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)
echo -------------------------------------------
echo  YouTube Chat Bot - Iniciando...
echo  Modo definido pelo config.yaml (obs.enabled)
echo -------------------------------------------
python gui_main.py
pause
