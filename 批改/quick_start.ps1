# 快速启动脚本 - 启动前端和后端批改工作流测试环境
# 使用方法: .\quick_start.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI 批改系统 - 快速启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python 是否安装
Write-Host "检查 Python 环境..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Python 已安装: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "✗ Python 未安装，请先安装 Python 3.11+" -ForegroundColor Red
    exit 1
}

# 检查 Node.js 是否安装
Write-Host "检查 Node.js 环境..." -ForegroundColor Yellow
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Node.js 已安装: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "✗ Node.js 未安装，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "步骤 1: 运行后端批改工作流测试" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "运行测试..." -ForegroundColor Yellow
python test_integration_local.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 后端测试失败" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✓ 后端测试完成，已生成 grading_results.json" -ForegroundColor Green
Write-Host ""

# 询问是否启动 API 服务器
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "步骤 2: 启动模拟 API 服务器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$startAPI = Read-Host "是否启动模拟 API 服务器? (y/n)"
if ($startAPI -eq "y" -or $startAPI -eq "Y") {
    Write-Host "启动 API 服务器..." -ForegroundColor Yellow
    Write-Host "API 地址: http://localhost:8001" -ForegroundColor Cyan
    Write-Host "API 文档: http://localhost:8001/docs" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
    Write-Host ""
    
    python mock_api_server.py
} else {
    Write-Host "跳过 API 服务器启动" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "步骤 3: 启动前端开发服务器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$startFrontend = Read-Host "是否启动前端开发服务器? (y/n)"
if ($startFrontend -eq "y" -or $startFrontend -eq "Y") {
    Write-Host "检查前端依赖..." -ForegroundColor Yellow
    
    if (-not (Test-Path "frontend/node_modules")) {
        Write-Host "安装前端依赖..." -ForegroundColor Yellow
        Set-Location frontend
        npm install
        Set-Location ..
    }
    
    Write-Host "启动前端服务器..." -ForegroundColor Yellow
    Write-Host "前端地址: http://localhost:3000" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Yellow
    Write-Host ""
    
    Set-Location frontend
    npm run dev
} else {
    Write-Host "跳过前端服务器启动" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "启动完成" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
