@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.22.3,<7"
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name WorkTool main.py
if errorlevel 1 goto :failed
echo Build complete. Distribute the entire dist\WorkTool folder, including _internal.
pause
exit /b 0
:failed
echo Build failed. Check the messages above.
pause
exit /b 1
