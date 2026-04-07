@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv\Scripts\python.exe
  echo Run installation first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m jayai.cli local-ui --open-browser
