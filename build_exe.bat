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
echo Construindo executavel...
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
echo Limpando arquivos temporarios...
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

echo.
echo Copiando config.yaml para junto do executavel...
copy /Y config.yaml dist\config.yaml

echo.
echo ============================================
echo  PRONTO! Executavel em: dist\YouTubeChatBot.exe
echo ============================================
pause
