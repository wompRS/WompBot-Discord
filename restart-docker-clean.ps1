<#
  restart-docker-clean.ps1

  Recovery for Docker Desktop failing to start on this machine with:
    "initializing Inference manager / Secrets Engine: listening on unix://...:
     The file cannot be accessed by the system.
     (listener: The filename, directory name, or volume label syntax is incorrect.)"

  Cause: Docker Desktop 4.73 creates AF_UNIX sockets (which are NTFS reparse
  points) under %LOCALAPPDATA%\Docker\run and %LOCALAPPDATA%\docker-secrets-engine.
  After an unclean stop (or a profile migration), those socket files are left as
  orphaned reparse points Windows can neither open nor delete, and each crashed
  boot leaves a new one that poisons the next boot.

  Fix: with Docker fully stopped, move ALL socket dirs aside at once so every
  socket path starts empty, then boot once. Docker recreates them cleanly.

  SAFE: only moves runtime socket directories. Never touches images, containers,
  volumes, settings, or any bot data.
#>

$ErrorActionPreference = 'Continue'
$dockerExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$local     = $env:LOCALAPPDATA
$ts        = Get-Date -Format 'yyyyMMdd-HHmmss'

Write-Host '1) Stopping Docker Desktop...' -ForegroundColor Cyan
Get-Process 'Docker Desktop','com.docker.backend','com.docker.cli','com.docker.build' -ErrorAction SilentlyContinue |
  ForEach-Object { try { $_.Kill() } catch {} }
Start-Sleep -Seconds 2
wsl.exe --shutdown 2>$null

Write-Host '2) Clearing stale AF_UNIX socket dirs...' -ForegroundColor Cyan
foreach ($dir in @("$local\Docker\run", "$local\docker-secrets-engine")) {
    if (Test-Path $dir) {
        $aside = "$dir.stale-$ts"
        try { Rename-Item -LiteralPath $dir -NewName (Split-Path $aside -Leaf) -ErrorAction Stop
              Write-Host "   moved aside: $dir" -ForegroundColor DarkGray }
        catch { Write-Host "   WARN could not move $dir : $($_.Exception.Message)" -ForegroundColor Yellow }
    } else { Write-Host "   absent (ok): $dir" -ForegroundColor DarkGray }
}

Write-Host '3) Starting Docker Desktop...' -ForegroundColor Cyan
Start-Process $dockerExe

Write-Host '4) Waiting for the engine (up to 4 min)...' -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(240); $ready = $false
while ((Get-Date) -lt $deadline) {
    $job = Start-Job { docker info --format '{{.ServerVersion}}' 2>$null }
    if (Wait-Job $job -Timeout 8) {
        $out = (Receive-Job $job) -join ''; Remove-Job $job -Force
        if ($out -and $out.Trim()) { Write-Host "   ENGINE READY (server $($out.Trim()))" -ForegroundColor Green; $ready = $true; break }
    } else { Stop-Job $job -EA SilentlyContinue; Remove-Job $job -Force -EA SilentlyContinue }
    Start-Sleep -Seconds 4
}
if (-not $ready) {
    Write-Host '   ENGINE NOT READY. Check the backend log:' -ForegroundColor Red
    Write-Host "   Get-Content '$local\Docker\log\host\com.docker.backend.exe.log' -Tail 30"
    return
}

Write-Host '5) Starting the bot stack...' -ForegroundColor Cyan
Push-Location $PSScriptRoot
docker compose up -d
docker compose ps
Pop-Location
Write-Host 'Done.' -ForegroundColor Green
