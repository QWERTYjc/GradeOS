# 本地环境快速设置脚本（Windows PowerShell）

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "AI 批改系统 - 本地环境设置" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""

# 检查 Docker
Write-Host "[1/5] 检查 Docker..." -ForegroundColor Yellow
$dockerRunning = docker info 2>$null
if (-not $dockerRunning) {
    Write-Host "  ✗ Docker 未运行，请先启动 Docker Desktop" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Docker 正在运行" -ForegroundColor Green

# 检查 .env 文件
Write-Host "`n[2/5] 检查环境变量..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "  ! 未找到 .env 文件，创建默认配置..." -ForegroundColor Yellow
    @"
# Database
DATABASE_URL=postgresql://grading_user:grading_pass@localhost:5432/grading_system

# Redis
REDIS_URL=redis://localhost:6379

# Offline Mode (set to false to use database/Redis)
OFFLINE_MODE=false

# Gemini API
GEMINI_API_KEY=your_api_key_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Worker Configuration
WORKER_CONCURRENCY=5
WORKER_POLL_INTERVAL=0.5
"@ | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "  ✓ 已创建 .env 文件，请编辑并填入 GEMINI_API_KEY" -ForegroundColor Green
}
else {
    Write-Host "  ✓ .env 文件已存在" -ForegroundColor Green
}

# 启动 Docker 服务
Write-Host "`n[3/5] 启动 Docker 服务..." -ForegroundColor Yellow
Write-Host "  启动 PostgreSQL 和 Redis..." -ForegroundColor Cyan
docker-compose up -d postgres redis

# 等待服务就绪
Write-Host "`n[4/5] 等待服务就绪..." -ForegroundColor Yellow
$maxWait = 30
$waited = 0
while ($waited -lt $maxWait) {
    $pgReady = docker-compose exec -T postgres pg_isready -U grading_user 2>$null
    $redisReady = docker-compose exec -T redis redis-cli ping 2>$null
    
    if ($pgReady -match "accepting connections" -and $redisReady -match "PONG") {
        Write-Host "  ✓ 所有服务已就绪" -ForegroundColor Green
        break
    }
    
    Write-Host "  等待中... ($waited/$maxWait 秒)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
    $waited += 2
}

if ($waited -ge $maxWait) {
    Write-Host "  ✗ 服务启动超时" -ForegroundColor Red
    exit 1
}

# 运行数据库迁移
Write-Host "`n[5/5] 运行数据库迁移..." -ForegroundColor Yellow
$env:OFFLINE_MODE = "false"
alembic upgrade head
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ 数据库迁移完成" -ForegroundColor Green
}
else {
    Write-Host "  ! 数据库迁移失败（可能是首次运行）" -ForegroundColor Yellow
}

# 完成
Write-Host "`n" -NoNewline
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host "设置完成！" -ForegroundColor Green
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 59) -ForegroundColor Cyan
Write-Host ""
Write-Host "服务信息：" -ForegroundColor Cyan
Write-Host "  PostgreSQL: localhost:5432" -ForegroundColor White
Write-Host "  Redis:      localhost:6379" -ForegroundColor White
Write-Host ""
Write-Host "启动应用：" -ForegroundColor Cyan
Write-Host "  python start_services.py --port 8002 --workers 2" -ForegroundColor White
Write-Host ""
Write-Host "或使用 Docker Compose 启动完整服务：" -ForegroundColor Cyan
Write-Host "  docker-compose up" -ForegroundColor White
Write-Host ""
