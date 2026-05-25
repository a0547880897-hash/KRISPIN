@echo off
chcp 65001 >nul
rem Windows - double-click this file to run
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)

%PY% --version >nul 2>nul
if %errorlevel% neq 0 (
  echo [!] Python is not installed. Download it from https://www.python.org/downloads/
  echo     During install, check "Add Python to PATH", then double-click this file again.
  pause
  exit /b 1
)

if not exist ".venv" (
  echo Installing ^(one time, takes a minute^)...
  %PY% -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip >nul
  .venv\Scripts\pip install -r requirements.txt
)

echo Starting... the browser will open at http://127.0.0.1:8000
echo (Keep this window open while downloading. To stop: Ctrl+C)
.venv\Scripts\python app.py
pause
