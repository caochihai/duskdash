[CmdletBinding()]
param(
    [switch]$Reload
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$backendRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Virtual environment not found. Run .\scripts\install.ps1 first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $backendRoot '.env.local'))) {
    throw 'Missing .env.local. Copy .env.example and replace every placeholder.'
}

$arguments = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000')
if ($Reload) {
    $arguments += '--reload'
}
Push-Location $backendRoot
try {
    & $python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
