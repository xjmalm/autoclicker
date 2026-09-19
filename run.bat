@echo off
setlocal
cd /d "%~dp0"

set "PYTHON="
set "PYTHON_ARGS="

where python >nul 2>nul
if %errorlevel%==0 set "PYTHON=python"

if not defined PYTHON (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON=py"
        set "PYTHON_ARGS=-3"
    )
)

if not defined PYTHON (
    set "BUNDLED_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if exist "%BUNDLED_PY%" set "PYTHON=%BUNDLED_PY%"
)

if not defined PYTHON (
    echo 未找到 Python，请先安装 Python 3.10 或更高版本。
    pause
    exit /b 1
)

"%PYTHON%" %PYTHON_ARGS% "%~dp0autoclicker.py" %*

if errorlevel 1 pause
