@echo off
:: Yap Windows Launcher
:: Detecta el intérprete Python embebido y lanza yap.py
setlocal

set "YAP_DIR=%~dp0"
set "PYTHON=%YAP_DIR%python\python.exe"
set "YAP_SCRIPT=%YAP_DIR%yap.py"
set "LLAMA_CLI=%YAP_DIR%bin\llama-cli.exe"

:: Verificar Python
if not exist "%PYTHON%" (
    echo ERROR: Python embebido no encontrado en %YAP_DIR%python\
    echo Reinstala Yap desde https://github.com/ChincoLinux/Yap/releases
    pause
    exit /b 1
)

:: Pasar llama-cli al agente via env var
set "PATH=%YAP_DIR%bin;%PATH%"
set "YAP_LLAMA_CLI=%LLAMA_CLI%"

:: Pasar argumentos y lanzar
"%PYTHON%" "%YAP_SCRIPT%" %*
