@echo off
REM ============================================
REM  INICIAR BOT DO YOUTUBE LIVE CHAT
REM ============================================
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)
echo -------------------------------------------
echo  YouTube Chat Bot - Iniciando...
echo -------------------------------------------
python youtube_chat_bot.py
pause
