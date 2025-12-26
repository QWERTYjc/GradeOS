# GradeOS Platform Development Startup Script

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GradeOS Platform - Development Mode  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Start Backend
Write-Host "`n[1/2] Starting Backend API..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\backend
    uvicorn src.api.main:app --reload --port 8001
}

# Start Frontend
Write-Host "[2/2] Starting Frontend..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\frontend
    npm run dev
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Services Starting...                  " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:3000       " -ForegroundColor White
Write-Host "  Backend:  http://localhost:8001/docs  " -ForegroundColor White
Write-Host "  Login:    teacher/123456              " -ForegroundColor White
Write-Host "            student/123456              " -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nPress Ctrl+C to stop all services" -ForegroundColor Gray

# Wait for jobs
try {
    while ($true) {
        Start-Sleep -Seconds 5
        Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
        Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue
    }
} finally {
    Stop-Job -Job $backendJob, $frontendJob
    Remove-Job -Job $backendJob, $frontendJob
}
