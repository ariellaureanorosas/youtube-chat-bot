@echo off
REM ============================================
REM  INICIAR BOT DO YOUTUBE COM OBS
REM  Inicia/para automaticamente com a transmissão
REM ============================================
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)
echo -------------------------------------------
echo  YouTube Chat Bot - Modo OBS
echo  Inicia e para automaticamente com o OBS
echo -------------------------------------------
echo.
echo  Se nao quiser o modo OBS, use:
echo    python obs_bot.py --no-obs
echo.
python obs_bot.py
pause
