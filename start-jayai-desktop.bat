@echo off
setlocal
set "ROOT=%~dp0"
set "DESKTOP_DIR=%ROOT%desktop"
cd /d "%DESKTOP_DIR%"

if not exist "node_modules" (
  call npm.cmd install
  if errorlevel 1 exit /b 1
)

call npm.cmd start
