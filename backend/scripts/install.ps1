[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$backendRoot = Split-Path -Parent $PSScriptRoot
Push-Location $backendRoot
try {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -eq $launcher) {
        throw 'Python launcher (py.exe) is required. Install Python 3.12 first.'
    }
    & py -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version"
    if ($LASTEXITCODE -ne 0) {
        throw 'Python 3.12 is required.'
    }
    & py -3.12 -m venv .venv
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
    & .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
