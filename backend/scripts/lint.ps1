[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$backendRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Virtual environment not found. Run .\scripts\install.ps1 first.'
}
Push-Location $backendRoot
try {
    & $python -m ruff check app tests
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    & $python -m mypy app
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
