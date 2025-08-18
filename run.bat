@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Install Python 3.9+ and re-run.
  pause
  exit /b 1
)
echo Installing dependencies (one-time)...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
echo Starting app...
python app_launcher.py
