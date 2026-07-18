[CmdletBinding()]
param(
    [switch]$Integration
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$backendRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Virtual environment not found. Run .\scripts\install.ps1 first.'
}
$arguments = @('-m', 'pytest')
if (-not $Integration) {
    $arguments += @('-m', 'not integration')
}
Push-Location $backendRoot
try {
    & $python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
