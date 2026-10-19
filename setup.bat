@echo off
cd /d "%~dp0"
set "WORKTOOL_PYTHON=python"
if not "%~1"=="" set "WORKTOOL_PYTHON=%~1"
"%WORKTOOL_PYTHON%" --version
if errorlevel 1 goto :failed
"%WORKTOOL_PYTHON%" -c "import sys, struct, sysconfig; sys.exit(0 if sys.implementation.name == 'cpython' and (3,11) <= sys.version_info[:2] < (3,16) and struct.calcsize('P') == 8 and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)"
if errorlevel 1 goto :failed
if not exist ".venv\Scripts\python.exe" "%WORKTOOL_PYTHON%" -m venv .venv
if errorlevel 1 goto :failed
echo Using the project environment:
".venv\Scripts\python.exe" --version
".venv\Scripts\python.exe" -c "import sys, struct, sysconfig; sys.exit(0 if sys.implementation.name == 'cpython' and (3,11) <= sys.version_info[:2] < (3,16) and struct.calcsize('P') == 8 and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)"
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo Setup complete. Open demo.bat to explore or start.bat for a fresh installation.
pause
exit /b 0
:failed
echo Setup failed. Use standard 64-bit CPython 3.11 through 3.15 and enable Add Python to PATH.
echo Free-threaded builds are not supported. Close WorkTool before upgrading dependencies.
echo An existing .venv keeps its Python version. See README.md to switch interpreters.
pause
exit /b 1
