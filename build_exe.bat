@echo off
REM ============================================
REM  BUILD YouTube Chat Bot GUI - EXE
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
echo  BUILD 1/2 — GUI (YouTubeChatBot.exe)
echo ============================================
pyinstaller --onefile --windowed --name "YouTubeChatBot" ^
    --add-data "gui;gui" ^
    --add-data "config.yaml;." ^
    --add-data "yt_status.png;." ^
    --collect-all playwright ^
    --collect-all aiohttp ^
    --hidden-import PySide6.QtNetwork ^
    --hidden-import qasync ^
    gui_main.py

echo.
echo ============================================
echo  BUILD 2/2 — OBS Launcher (YouTubeChatBot-OBS.exe)
echo ============================================
pyinstaller --onefile --console --name "YouTubeChatBot-OBS" ^
    --add-data "config.yaml;." ^
    --add-data "yt_status.png;." ^
    --collect-all playwright ^
    --collect-all aiohttp ^
    --hidden-import obs_tray ^
    obs_bot.py

echo.
echo Limpando arquivos temporarios...
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

echo.
echo Copiando config.yaml para junto dos executaveis...
copy /Y config.yaml dist\config.yaml

echo.
echo ============================================
echo  PRONTO!
echo    dist\YouTubeChatBot.exe     (GUI — modo normal)
echo    dist\YouTubeChatBot-OBS.exe (Console — modo OBS)
echo ============================================
pause
