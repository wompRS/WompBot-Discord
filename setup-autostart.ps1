# Quick Setup Script for Discord Bot Auto-Start
# Run this script as Administrator to automatically configure auto-start

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Discord Bot Auto-Start Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "To run as Administrator:" -ForegroundColor Yellow
    Write-Host "1. Right-click on PowerShell" -ForegroundColor Yellow
    Write-Host "2. Select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host "3. Navigate to E:\discord-bot" -ForegroundColor Yellow
    Write-Host "4. Run: .\setup-autostart.ps1" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if WSL is installed
Write-Host "Checking prerequisites..." -ForegroundColor Yellow
try {
    $wslVersion = wsl --version 2>&1
    Write-Host "[OK] WSL is installed" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] WSL is not installed" -ForegroundColor Red
    Write-Host "Please install WSL first: wsl --install" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if Debian is installed
$debianInstalled = wsl -l -q | Select-String "Debian"
if (-not $debianInstalled) {
    Write-Host "[WARNING] Debian not found in WSL" -ForegroundColor Yellow
    Write-Host "Available distributions:" -ForegroundColor Yellow
    wsl -l -v
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        exit 1
    }
} else {
    Write-Host "[OK] Debian found in WSL" -ForegroundColor Green
}

# Check if Docker is installed in WSL
Write-Host "Checking Docker in WSL..." -ForegroundColor Yellow
$dockerCheck = wsl -d Debian bash -c "command -v docker" 2>&1
if (-not $dockerCheck) {
    Write-Host "[WARNING] Docker not found in WSL Debian" -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        exit 1
    }
} else {
    Write-Host "[OK] Docker found in WSL" -ForegroundColor Green
}

Write-Host ""
Write-Host "Setting up auto-start task..." -ForegroundColor Cyan

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName "Discord Bot Auto-Start" -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host ""
    Write-Host "Task 'Discord Bot Auto-Start' already exists!" -ForegroundColor Yellow
    $overwrite = Read-Host "Overwrite existing task? (y/n)"
    if ($overwrite -eq "y") {
        Unregister-ScheduledTask -TaskName "Discord Bot Auto-Start" -Confirm:$false
        Write-Host "Removed existing task" -ForegroundColor Yellow
    } else {
        Write-Host "Setup cancelled" -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 0
    }
}

# Import the task from XML
Write-Host "Importing scheduled task..." -ForegroundColor Yellow
try {
    Register-ScheduledTask -Xml (Get-Content "E:\discord-bot\discord-bot-autostart-task.xml" | Out-String) -TaskName "Discord Bot Auto-Start" -Force
    Write-Host "[OK] Task created successfully!" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to create task: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "The Discord bot will now start automatically on system boot." -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Test the task by running it manually (see below)" -ForegroundColor White
Write-Host "2. Restart your computer to test auto-start" -ForegroundColor White
Write-Host "3. Check logs with: docker-compose logs -f bot" -ForegroundColor White
Write-Host ""

$testNow = Read-Host "Test the task now? (y/n)"
if ($testNow -eq "y") {
    Write-Host ""
    Write-Host "Running task..." -ForegroundColor Yellow
    Start-ScheduledTask -TaskName "Discord Bot Auto-Start"
    Start-Sleep -Seconds 5

    Write-Host ""
    Write-Host "Checking container status..." -ForegroundColor Yellow
    wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose ps"

    Write-Host ""
    Write-Host "To view logs:" -ForegroundColor Cyan
    Write-Host "wsl -d Debian bash -c 'cd /mnt/e/discord-bot && docker-compose logs -f bot'" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete! See AUTOSTART_SETUP.md for more details." -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"
