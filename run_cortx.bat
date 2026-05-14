@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "VENV_DIR=%CD%\cortx-venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "REQ_HASH_FILE=%VENV_DIR%\requirements.sha256"
set "MODEL_NAME=llama3.1:8b-instruct-q5_K_M"
set "OLLAMA_TAGS_URL=http://localhost:11434/api/tags"

if not exist "%PYTHON_EXE%" (
    echo [INFO] Creating virtual environment: cortx-venv
    py -3 -m venv "%VENV_DIR%"
    if errorlevel 1 goto :error
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 goto :error

call :ensure_dependencies
if errorlevel 1 goto :error

echo [INFO] Ensuring Playwright Chromium is installed...
python -m playwright install chromium
if errorlevel 1 goto :error

where ollama >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Ollama was not found in PATH.
    echo [ERROR] Install Ollama, then rerun this script.
    goto :error
)

echo [INFO] Checking Ollama model: %MODEL_NAME%
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; $resp=Invoke-RestMethod -Method Get -Uri '%OLLAMA_TAGS_URL%' -TimeoutSec 5; $names=@(); if ($resp.models) { $names = $resp.models | ForEach-Object { $_.name } }; if ($names -contains '%MODEL_NAME%') { exit 0 } else { exit 2 }"
set "MODEL_CHECK_RESULT=%ERRORLEVEL%"

if "%MODEL_CHECK_RESULT%"=="1" (
    echo [ERROR] Ollama service is not reachable at %OLLAMA_TAGS_URL%.
    echo [ERROR] Start Ollama and rerun this script.
    goto :error
)

if "%MODEL_CHECK_RESULT%"=="2" (
    echo [INFO] Pulling Ollama model %MODEL_NAME%...
    ollama pull "%MODEL_NAME%"
    if errorlevel 1 goto :error
) else (
    echo [INFO] Model already available.
)

if "%~1"=="" goto :run_interactive
if /I "%~1"=="--query" goto :run_query_mode

echo [INFO] Starting Cortx with provided arguments...
python main.py %*
goto :eof

:run_interactive
echo [INFO] Starting Cortx GUI...
python main.py --gui
goto :eof

:run_query_mode
shift
if "%~1"=="" (
    echo [ERROR] Missing query text after --query.
    goto :error
)

set "QUERY="
:collect_query
if "%~1"=="" goto :run_query

set "TOKEN=%~1"
set "TOKEN=!TOKEN:"=!"
if "!TOKEN:~0,1!"=="\" set "TOKEN=!TOKEN:~1!"
if "!TOKEN:~-1!"=="\" set "TOKEN=!TOKEN:~0,-1!"

if defined QUERY (
    set "QUERY=!QUERY! !TOKEN!"
) else (
    set "QUERY=!TOKEN!"
)

shift
goto :collect_query

:run_query
echo [INFO] Starting Cortx with query text...
python main.py --query "!QUERY!"
goto :eof

goto :eof

:ensure_dependencies
for /f %%H in ('powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 'requirements.txt').Hash"') do set "CURRENT_REQ_HASH=%%H"

if not defined CURRENT_REQ_HASH (
    echo [ERROR] Unable to compute requirements.txt hash.
    exit /b 1
)

set "NEEDS_INSTALL=1"
if exist "%REQ_HASH_FILE%" (
    set /p STORED_REQ_HASH=<"%REQ_HASH_FILE%"
    if /I "!STORED_REQ_HASH!"=="!CURRENT_REQ_HASH!" set "NEEDS_INSTALL=0"
)

if "!NEEDS_INSTALL!"=="1" (
    echo [INFO] Dependency changes detected. Installing/updating dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
    >"%REQ_HASH_FILE%" echo !CURRENT_REQ_HASH!
) else (
    echo [INFO] Dependencies unchanged. Skipping pip install.
)

exit /b 0

:error
echo [ERROR] Setup or startup failed.
exit /b 1
