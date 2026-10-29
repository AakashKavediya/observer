# scripts/build_all.ps1
# Complete end-to-end production build pipeline:
# 1. Fetch models
# 2. Build Python sidecar
# 3. Build React UI
# 4. Build Tauri host binary / installer
[CmdletBinding()]
param(
    [switch]$SkipEngine = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "   Observer Full Production Build       " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Step 1: Model verification
Write-Host "`n[Step 1/4] Verifying MediaPipe model assets..." -ForegroundColor Yellow
python (Join-Path $ScriptDir "fetch_models.py")

# Step 2: Build Engine
if (-not $SkipEngine) {
    Write-Host "`n[Step 2/4] Building Python engine sidecar..." -ForegroundColor Yellow
    & (Join-Path $ScriptDir "build_engine.ps1")
} else {
    Write-Host "`n[Step 2/4] Skipping engine build (flag -SkipEngine specified)." -ForegroundColor Gray
}

# Step 3: Frontend Build
Write-Host "`n[Step 3/4] Building React 18 TypeScript frontend..." -ForegroundColor Yellow
Push-Location $ProjectRoot
try {
    npm run build
}
finally {
    Pop-Location
}

# Step 4: Tauri Build
Write-Host "`n[Step 4/4] Building Tauri desktop package..." -ForegroundColor Yellow
Push-Location $ProjectRoot
try {
    npm run tauri build
}
finally {
    Pop-Location
}

Write-Host "`n[SUCCESS] Production build completed!" -ForegroundColor Green
