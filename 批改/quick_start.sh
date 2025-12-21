#!/bin/bash
# 快速启动脚本 - 启动前端和后端批改工作流测试环境
# 使用方法: bash quick_start.sh

set -e

echo "========================================"
echo "AI 批改系统 - 快速启动脚本"
echo "========================================"
echo ""

# 检查 Python 是否安装
echo "检查 Python 环境..."
if ! command -v python &> /dev/null; then
    echo "✗ Python 未安装，请先安装 Python 3.11+"
    exit 1
fi
PYTHON_VERSION=$(python --version)
echo "✓ Python 已安装: $PYTHON_VERSION"

# 检查 Node.js 是否安装
echo "检查 Node.js 环境..."
if ! command -v node &> /dev/null; then
    echo "✗ Node.js 未安装，请先安装 Node.js 18+"
    exit 1
fi
NODE_VERSION=$(node --version)
echo "✓ Node.js 已安装: $NODE_VERSION"

echo ""
echo "========================================"
echo "步骤 1: 运行后端批改工作流测试"
echo "========================================"
echo ""

echo "运行测试..."
python test_integration_local.py

if [ $? -ne 0 ]; then
    echo "✗ 后端测试失败"
    exit 1
fi

echo ""
echo "✓ 后端测试完成，已生成 grading_results.json"
echo ""

# 询问是否启动 API 服务器
echo "========================================"
echo "步骤 2: 启动模拟 API 服务器"
echo "========================================"
echo ""

read -p "是否启动模拟 API 服务器? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "启动 API 服务器..."
    echo "API 地址: http://localhost:8001"
    echo "API 文档: http://localhost:8001/docs"
    echo ""
    echo "按 Ctrl+C 停止服务器"
    echo ""
    
    python mock_api_server.py
else
    echo "跳过 API 服务器启动"
fi

echo ""
echo "========================================"
echo "步骤 3: 启动前端开发服务器"
echo "========================================"
echo ""

read -p "是否启动前端开发服务器? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "检查前端依赖..."
    
    if [ ! -d "frontend/node_modules" ]; then
        echo "安装前端依赖..."
        cd frontend
        npm install
        cd ..
    fi
    
    echo "启动前端服务器..."
    echo "前端地址: http://localhost:3000"
    echo ""
    echo "按 Ctrl+C 停止服务器"
    echo ""
    
    cd frontend
    npm run dev
else
    echo "跳过前端服务器启动"
fi

echo ""
echo "========================================"
echo "启动完成"
echo "========================================"
