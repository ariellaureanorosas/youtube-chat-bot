@echo off
REM ============================================
REM  BUILD YouTube Chat Bot - EXE UNIFICADO
REM  Gera um unico executavel com suporte
REM  a modo manual e OBS (configuravel via config.yaml)
REM ============================================
cd /d "%~dp0"

REM Mata processos stale do bot que podem travar o build
echo Verificando processos stale do bot...
taskkill /F /IM YouTubeChatBot.exe 2>nul && echo   -> Processo antigo encerrado. || echo   -> Nenhum processo rodando.

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo Instalando PyInstaller...
pip install pyinstaller

echo.
echo ============================================
echo  BUILD — YouTubeChatBot.exe (GUI Unificada)
echo ============================================
pyinstaller --onefile --windowed --name "YouTubeChatBot" ^
    --add-data "gui;gui" ^
    --add-data "config.yaml;." ^
    --add-data "yt_status.png;." ^
    --collect-all playwright ^
    --collect-all aiohttp ^
    --hidden-import PySide6.QtNetwork ^
    --hidden-import qasync ^
    --hidden-import obsws_python ^
    --hidden-import pystray ^
    --hidden-import PIL._tkinter_finder ^
    gui_main.py

echo.
echo Copiando config.yaml para junto do executavel...
copy /Y config.yaml dist\config.yaml

echo.
echo ============================================
echo  PRONTO!
echo    dist\YouTubeChatBot.exe  (GUI Unificada)
echo  Use --obs para forçar modo OBS, ou
echo  configure obs.enabled no config.yaml
echo ============================================
pause
