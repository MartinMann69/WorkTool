param([string]$InnoCompiler = '')
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $taskRoot
$python = Join-Path $taskRoot '.venv\Scripts\python.exe'
$env:PYINSTALLER_CONFIG_DIR = Join-Path $taskRoot '.build-tools\pyinstaller-cache'
& $python scripts\build_icon.py
if ($LASTEXITCODE -ne 0) { throw 'Could not create application icon.' }
& $python -m PyInstaller --noconfirm --distpath dist --workpath build packaging\TSLibrary.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
if (-not $InnoCompiler) {
    $candidates = @(
        (Join-Path $taskRoot '.build-tools\InnoSetup\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
    )
    $InnoCompiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $InnoCompiler) { throw 'The standalone app is in dist\TSLibrary. Install Inno Setup 6 and rerun with -InnoCompiler pointing to ISCC.exe to build the installer.' }
& $InnoCompiler packaging\TSLibrary.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
Write-Output (Join-Path $taskRoot 'dist\TSLibrary-Setup-0.2.0.exe')
