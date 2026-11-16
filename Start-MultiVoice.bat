@echo off
rem ============================================================
rem  MultiVoice Summary Suit - trial launcher
rem  Double-click to start, or drag a media file onto this .bat
rem  to transcribe it immediately.
rem ============================================================
setlocal
cd /d "%~dp0"
title MultiVoice Summary Suit

set "PYTHONPATH=%~dp0src"
set "PYW=D:\Local Repositories\_venvs\MultiVoice-Summary-Suit\Scripts\pythonw.exe"
set "PY=D:\Local Repositories\_venvs\MultiVoice-Summary-Suit\Scripts\python.exe"

if not exist "%PYW%" (
  echo [ERROR] Python environment not found:
  echo         %PYW%
  echo.
  echo Create it first, then run this file again.
  pause
  exit /b 1
)

echo Checking environment...
"%PY%" -c "import PySide6, multivoice" >nul 2>&1
if errorlevel 1 (
  echo [ERROR] The environment is incomplete. Run this to repair it:
  echo         uv pip install --python "%PY%" PySide6
  pause
  exit /b 1
)

echo Starting tray app...
if "%~1"=="" (
  start "" "%PYW%" -m multivoice.ui.tray
) else (
  start "" "%PYW%" -m multivoice.ui.tray --input "%~1"
)

timeout /t 3 >nul
echo.
echo Done. Look for the blue sound-wave icon in the notification area.
echo Right-click it to transcribe a file.
echo.
if "%~1"=="" (
  echo Tip: drag a video or audio file onto this .bat to start immediately.
)
timeout /t 5 >nul
exit /b 0
