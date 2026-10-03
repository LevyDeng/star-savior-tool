@echo off
cd /d "%~dp0"
if not exist .runtime\tmp mkdir .runtime\tmp
set "TEMP=%CD%\.runtime\tmp"
set "TMP=%TEMP%"
if not exist .venv\Scripts\python.exe py -3.11 -m venv .venv
.venv\Scripts\python.exe -c "import PySide6, rapidocr, onnxruntime, PIL" >nul 2>&1
if errorlevel 1 .venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m star_savior
pause
