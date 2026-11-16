@echo off
rem Start the MultiVoice Summary Suit tray app.
rem Override the interpreter with MVS_PYTHON if the venv lives elsewhere.
setlocal
set "PYTHONPATH=%~dp0src"

if defined MVS_PYTHON (
  "%MVS_PYTHON%" -m multivoice.ui.tray %*
  goto :eof
)

set "VENV=D:\Local Repositories\_venvs\MultiVoice-Summary-Suit\Scripts\pythonw.exe"
if exist "%VENV%" (
  "%VENV%" -m multivoice.ui.tray %*
) else (
  pythonw -m multivoice.ui.tray %*
)

