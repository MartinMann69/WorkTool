@echo off
cd /d "%~dp0"
python --version
if errorlevel 1 goto :failed
python -c "import sys, struct; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,14) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 goto :failed
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo Setup complete. Open demo.bat to explore or start.bat for a fresh installation.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.11, 3.12 or 3.13 and enable Add Python to PATH.
pause
exit /b 1
