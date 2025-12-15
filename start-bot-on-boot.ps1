# Discord Bot Auto-Start Script
# This script starts WSL Debian and launches the Discord bot container
# To be run on Windows startup via Task Scheduler

# Enable verbose output
$VerbosePreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Discord Bot Auto-Start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Wait for network to be ready (important on boot)
Write-Host "Waiting for network..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check if WSL is installed
Write-Host "Checking WSL installation..." -ForegroundColor Yellow
try {
    $wslVersion = wsl --version
    Write-Host "WSL is installed" -ForegroundColor Green
} catch {
    Write-Host "ERROR: WSL is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Start WSL Debian (this ensures it's running)
Write-Host "Starting WSL Debian..." -ForegroundColor Yellow
wsl -d Debian echo "WSL Debian is running"

# Wait a moment for WSL to fully initialize
Start-Sleep -Seconds 3

# Check if Docker is installed in WSL
Write-Host "Checking Docker installation..." -ForegroundColor Yellow
$dockerCheck = wsl -d Debian bash -c "command -v docker"
if (-not $dockerCheck) {
    Write-Host "ERROR: Docker not found in WSL Debian" -ForegroundColor Red
    exit 1
}
Write-Host "Docker found in WSL" -ForegroundColor Green

# Start Docker daemon if not running
Write-Host "Starting Docker daemon..." -ForegroundColor Yellow
wsl -d Debian sudo service docker start
Start-Sleep -Seconds 5

# Verify Docker is running
Write-Host "Verifying Docker status..." -ForegroundColor Yellow
$dockerStatus = wsl -d Debian sudo service docker status
Write-Host $dockerStatus

# Navigate to bot directory and start containers
Write-Host "Starting Discord bot containers..." -ForegroundColor Yellow
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose up -d"

# Check container status
Write-Host ""
Write-Host "Container status:" -ForegroundColor Cyan
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose ps"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Discord bot startup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To view logs: wsl -d Debian bash -c 'cd /mnt/e/discord-bot && docker-compose logs -f bot'" -ForegroundColor Yellow
