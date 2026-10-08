# Windows PowerShell Production Launcher
$ErrorActionPreference = "Stop"
Write-Host "=====================================================" -ForegroundColor Green
Write-Host " Starting Travel Guide Production App (Waitress WSGI)" -ForegroundColor Green
Write-Host " URL: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host " Health: http://127.0.0.1:5000/api/health" -ForegroundColor Cyan
Write-Host " Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Green

& ".\.venv\Scripts\python.exe" wsgi.py
