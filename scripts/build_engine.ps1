# scripts/build_engine.ps1
# Builds the Python engine sidecar using PyInstaller (onedir mode)
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$EngineDir = Join-Path $ProjectRoot "engine"

Write-Host "=== Building Observer Engine Sidecar ===" -ForegroundColor Cyan

# 1. Ensure model is present
Write-Host "1. Fetching MediaPipe models..."
python (Join-Path $ScriptDir "fetch_models.py")

# 2. Install requirements in virtual environment if needed
Push-Location $EngineDir
try {
    Write-Host "2. Running PyInstaller with observer_engine.spec..."
    pyinstaller --clean --noconfirm observer_engine.spec

    $TargetDir = Join-Path $EngineDir "dist\observer-engine"
    if (Test-Path $TargetDir) {
        Write-Host "Engine sidecar built successfully at: $TargetDir" -ForegroundColor Green
    } else {
        throw "Build output not found at $TargetDir"
    }
}
finally {
    Pop-Location
}
