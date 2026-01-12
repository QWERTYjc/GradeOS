#!/usr/bin/env python3
"""
后端快速启动脚本

用法:
  python run.py              # 启动开发服务器
  python run.py --port 8001  # 指定端口
  python run.py --help       # 显示帮助
"""

import sys
import subprocess
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="GradeOS 后端启动脚本")
    parser.add_argument("--port", type=int, default=8001, help="服务器端口 (默认: 8001)")
    parser.add_argument("--host", default="0.0.0.0", help="服务器地址 (默认: 0.0.0.0)")
    parser.add_argument("--reload", action="store_true", default=True, help="启用自动重载 (默认: 启用)")
    parser.add_argument("--no-reload", dest="reload", action="store_false", help="禁用自动重载")
    
    args = parser.parse_args()
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.api.main:app",
        "--host", args.host,
        "--port", str(args.port),
    ]
    
    if args.reload:
        cmd.append("--reload")
    
    print(f"启动 FastAPI 服务器...")
    print(f"地址: http://{args.host}:{args.port}")
    print(f"API 文档: http://{args.host}:{args.port}/docs")
    print(f"命令: {' '.join(cmd)}\n")
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
