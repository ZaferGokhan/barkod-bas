@echo off
cd /d "%~dp0"
set "PY=C:\Python\Python312\python.exe"
set "PYW=C:\Python\Python312\pythonw.exe"
if not exist "%PY%" set "PY=python"
if not exist "%PYW%" set "PYW=%PY%"
"%PY%" -c "import openpyxl, serial, PIL" 2>nul
if errorlevel 1 (
  "%PY%" -m pip install -r "%~dp0requirements.txt"
)
start "" "%PYW%" "%~dp0barkod_bas.py"
