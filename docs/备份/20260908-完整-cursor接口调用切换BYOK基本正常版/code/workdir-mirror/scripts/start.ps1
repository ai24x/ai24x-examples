# AI24X Website - Permanent Online Startup (PowerShell)
# UTF-8 encoding, works on all Windows versions

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI24X Website - Permanent Online Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# 1. Check Node.js
Write-Host "1. Checking Node.js version..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "   Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "   ERROR: Node.js not installed or not in PATH" -ForegroundColor Red
    Write-Host "   Please install Node.js from https://nodejs.org/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# 2. Check/Install PM2
Write-Host "2. Checking PM2 installation..." -ForegroundColor Yellow
try {
    $pm2Version = pm2 --version
    Write-Host "   PM2: $pm2Version" -ForegroundColor Green
} catch {
    Write-Host "   WARNING: PM2 not installed, installing now..." -ForegroundColor Yellow
    try {
        npm install -g pm2
        Write-Host "   OK: PM2 installed successfully" -ForegroundColor Green
    } catch {
        Write-Host "   ERROR: PM2 installation failed" -ForegroundColor Red
        Write-Host "   Please check npm permissions or run as administrator" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# 3. Start AI24X service
Write-Host "3. Starting AI24X permanent online service..." -ForegroundColor Yellow
try {
    pm2 start server-permanent.js --name ai24x --watch --max-memory-restart 200M
    Write-Host "   OK: Service started successfully" -ForegroundColor Green
} catch {
    Write-Host "   ERROR: Service startup failed" -ForegroundColor Red
    Write-Host "   Please check the error message above" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# 4. Setup auto-start
Write-Host "4. Setting up auto-start on boot..." -ForegroundColor Yellow
try {
    pm2 startup
    pm2 save
    Write-Host "   OK: Auto-start configured" -ForegroundColor Green
} catch {
    Write-Host "   WARNING: Auto-start configuration failed" -ForegroundColor Yellow
    Write-Host "   Service will not start automatically on boot" -ForegroundColor Yellow
}

# 5. Show status
Write-Host "5. Showing service status..." -ForegroundColor Yellow
pm2 status ai24x

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SUCCESS: AI24X permanent online service started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "ACCESS URLs:" -ForegroundColor Cyan
Write-Host "  Local:    http://localhost:3000" -ForegroundColor White
Write-Host "  Public:   http://42.192.1.93:3000" -ForegroundColor White
Write-Host "  Health:   http://localhost:3000/health" -ForegroundColor White
Write-Host "  Status:   http://localhost:3000/status" -ForegroundColor White

Write-Host ""
Write-Host "MANAGEMENT COMMANDS:" -ForegroundColor Cyan
Write-Host "  pm2 status ai24x      - Check status" -ForegroundColor White
Write-Host "  pm2 logs ai24x        - View logs" -ForegroundColor White
Write-Host "  pm2 restart ai24x     - Restart service" -ForegroundColor White
Write-Host "  pm2 stop ai24x        - Stop service" -ForegroundColor White
Write-Host "  pm2 delete ai24x      - Delete service" -ForegroundColor White

Write-Host ""
Write-Host "INFO: Service will auto-start on system boot" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to exit"