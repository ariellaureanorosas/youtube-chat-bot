@echo off
REM ============================================
REM  INICIAR BOT DO YOUTUBE COM OBS
REM  Forca modo OBS (inicia/para com a transmissao)
REM ============================================
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)
echo -------------------------------------------
echo  YouTube Chat Bot - Modo OBS (forcado)
echo  Inicia e para automaticamente com o OBS
echo -------------------------------------------
echo.
echo  Dica: para alternar, edite config.yaml
echo    ou remova a flag --obs deste script
echo.
python gui_main.py --obs
pause
