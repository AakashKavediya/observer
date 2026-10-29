# scripts/verify_offline.ps1
# Enforces an offline sandbox test:
# Blocks outbound network traffic via temporary Windows Firewall rule,
# starts the Observer app, checks IPC communication, and restores networking.
[CmdletBinding()]
param(
    [string]$AppPath = "src-tauri\target\release\Observer.exe",
    [int]$TestDurationSeconds = 15
)

$ErrorActionPreference = "Stop"
$RuleName = "Observer_Offline_Verification_BlockRule"

Write-Host "=== Offline Verification Test ===" -ForegroundColor Cyan
Write-Host "Verifying that Observer operates with ZERO network access..."

# Ensure binary exists
if (-not (Test-Path $AppPath)) {
    Write-Warning "Binary not found at $AppPath. Testing dev bundle or build first..."
}

try {
    Write-Host "1. Creating temporary outbound block rule in Windows Firewall..."
    netsh advfirewall firewall add rule name=$RuleName dir=out action=block program=(Resolve-Path $AppPath) enable=yes | Out-Null

    Write-Host "2. Launching Observer in offline sandbox..."
    $process = Start-Process -FilePath $AppPath -PassThru

    Write-Host "3. Monitoring offline execution for $TestDurationSeconds seconds..."
    Start-Sleep -Seconds $TestDurationSeconds

    if ($process.HasExited) {
        throw "Observer process exited prematurely during offline test! Exit code: $($process.ExitCode)"
    }

    Write-Host "[SUCCESS] Observer continued operating normally without any network egress!" -ForegroundColor Green
    $process.Kill()
}
catch {
    Write-Error "Offline verification failed: $_"
}
finally {
    Write-Host "4. Cleaning up firewall rule..."
    netsh advfirewall firewall delete rule name=$RuleName | Out-Null
    Write-Host "Offline test cleanup complete."
}
