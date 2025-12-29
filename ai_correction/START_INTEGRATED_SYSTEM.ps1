# BookScan-AI 与批改系统集成 - 快速启动脚本
# PowerShell Script for Windows

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     BookScan-AI Integration System - Quick Start             ║" -ForegroundColor Cyan
Write-Host "║          AI GURU: NEXT GEN GRADING SYSTEM v2.0               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

Write-Host ""
Write-Host "📋 系统检查中..." -ForegroundColor Yellow

# 检查 Python
Write-Host "✓ 检查 Python..." -ForegroundColor Gray
python --version 2>$null
if (-not $?) {
    Write-Host "❌ Python 未安装，请先安装 Python 3.8+" -ForegroundColor Red
    exit 1
}

# 检查依赖
Write-Host "✓ 检查依赖..." -ForegroundColor Gray
$required_packages = @("streamlit", "pillow", "pandas")
foreach ($package in $required_packages) {
    python -c "import ${package}" 2>$null
    if (-not $?) {
        Write-Host "⚠️  安装缺失的包: $package" -ForegroundColor Yellow
        pip install $package -q
    }
}

Write-Host ""
Write-Host "🚀 启动系统..." -ForegroundColor Green
Write-Host ""

# 显示访问信息
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "📱 系统已启动!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

Write-Host ""
Write-Host "🌐 访问地址:" -ForegroundColor Yellow
Write-Host "   Local:   http://localhost:8501" -ForegroundColor Cyan
Write-Host "   Network: http://192.168.0.100:8501" -ForegroundColor Cyan

Write-Host ""
Write-Host "🔐 登录凭证:" -ForegroundColor Yellow
Write-Host "   用户名: demo" -ForegroundColor Cyan
Write-Host "   密码:   demo" -ForegroundColor Cyan

Write-Host ""
Write-Host "📖 新功能导航:" -ForegroundColor Yellow
Write-Host "   📱 SCANNER      - BookScan-AI 扫描引擎集成" -ForegroundColor Cyan
Write-Host "   🔗 API DEMO     - 实时 API 调用监控" -ForegroundColor Cyan
Write-Host "   📝 GRADING      - AI 智能批改引擎" -ForegroundColor Cyan
Write-Host "   📚 HISTORY      - 批改历史记录" -ForegroundColor Cyan

Write-Host ""
Write-Host "📊 集成系统特性:" -ForegroundColor Yellow
Write-Host "   ✅ 手机扫描引擎 (高分辨率 4096×2160)" -ForegroundColor Green
Write-Host "   ✅ 自动边缘检测 (4% 边距移除)" -ForegroundColor Green
Write-Host "   ✅ 双页书本分割 (智能中缝识别)" -ForegroundColor Green
Write-Host "   ✅ 多模态 AI 批改 (8 个智能 Agent)" -ForegroundColor Green
Write-Host "   ✅ 实时 API 监控 (性能追踪)" -ForegroundColor Green
Write-Host "   ✅ 完整工作流管理 (端到端 4.8 秒)" -ForegroundColor Green

Write-Host ""
Write-Host "📚 快速指南:" -ForegroundColor Yellow
Write-Host "   1. 打开浏览器访问上述地址" -ForegroundColor Cyan
Write-Host "   2. 使用 demo/demo 登录" -ForegroundColor Cyan
Write-Host "   3. 点击 '📱 SCANNER' 查看扫描功能" -ForegroundColor Cyan
Write-Host "   4. 点击 '🔗 API DEMO' 观看 API 演示" -ForegroundColor Cyan
Write-Host "   5. 点击 '📝 GRADING' 开始批改" -ForegroundColor Cyan

Write-Host ""
Write-Host "💡 提示:" -ForegroundColor Yellow
Write-Host "   • 按 Ctrl+C 停止应用" -ForegroundColor Gray
Write-Host "   • 查看 INTEGRATION_DEMO_REPORT.md 了解详细信息" -ForegroundColor Gray
Write-Host "   • 查看 BOOKSCAN_INTEGRATION_GUIDE.md 了解技术细节" -ForegroundColor Gray

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# 启动应用
streamlit run main.py --logger.level=warning
