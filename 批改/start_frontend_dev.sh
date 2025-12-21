#!/bin/bash
# 前端开发启动脚本

echo "启动前端开发服务器..."
echo "================================================"

cd frontend

# 检查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    echo "安装依赖..."
    npm install
fi

# 启动开发服务器
echo "前端服务器启动在: http://localhost:3000"
echo "================================================"
npm run dev
