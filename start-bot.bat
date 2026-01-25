@echo off
REM Start Discord bot containers via Docker Desktop
REM Wait for Docker Desktop to be ready

echo Waiting for Docker Desktop to start...

:WAIT_DOCKER
docker info >nul 2>&1
if errorlevel 1 (
    timeout /t 5 /nobreak >nul
    goto WAIT_DOCKER
)

echo Docker Desktop is ready. Starting containers...
cd /d E:\discord-bot
docker compose up -d

echo Bot started successfully.
