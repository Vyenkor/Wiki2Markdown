@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_dependencies.ps1"
if errorlevel 1 (
  echo.
  echo Dependency installation failed.
  pause
  exit /b 1
)
echo.
echo Dependency installation finished.
pause
