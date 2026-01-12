#!/usr/bin/env python3
"""
GradeOS Platform 开发环境启动脚本

支持同时启动后端和前端服务
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    """打印标题"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(text):
    """打印成功信息"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")

def print_info(text):
    """打印信息"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")

def print_warning(text):
    """打印警告"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")

def print_error(text):
    """打印错误"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")

def check_python_version():
    """检查 Python 版本"""
    print_info("检查 Python 版本...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print_error(f"需要 Python 3.11+，当前版本: {version.major}.{version.minor}")
        sys.exit(1)
    print_success(f"Python 版本: {version.major}.{version.minor}.{version.micro}")

def check_node_version():
    """检查 Node.js 版本"""
    print_info("检查 Node.js 版本...")
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print_success(f"Node.js 版本: {result.stdout.strip()}")
        else:
            print_warning("未找到 Node.js，跳过前端检查")
    except FileNotFoundError:
        print_warning("未找到 Node.js，跳过前端检查")

def check_backend_env():
    """检查后端环境"""
    print_info("检查后端环境...")
    
    # 检查 .env 文件
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        print_warning(f".env 文件不存在: {env_file}")
        print_info("使用 .env.example 作为参考")
        example_file = BACKEND_DIR / ".env.example"
        if example_file.exists():
            print_info(f"请复制 {example_file} 到 {env_file}")
    else:
        print_success(f".env 文件存在")
    
    # 检查依赖
    requirements_file = BACKEND_DIR / "requirements.txt"
    if requirements_file.exists():
        print_success(f"requirements.txt 存在")
    else:
        print_warning(f"requirements.txt 不存在: {requirements_file}")

def check_frontend_env():
    """检查前端环境"""
    print_info("检查前端环境...")
    
    # 检查 package.json
    package_file = FRONTEND_DIR / "package.json"
    if package_file.exists():
        print_success(f"package.json 存在")
    else:
        print_warning(f"package.json 不存在: {package_file}")

def start_backend():
    """启动后端服务"""
    print_header("启动后端服务")
    
    os.chdir(BACKEND_DIR)
    
    # 检查是否需要安装依赖
    venv_dir = BACKEND_DIR / "venv"
    if not venv_dir.exists():
        print_info("虚拟环境不存在，创建虚拟环境...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print_success("虚拟环境创建完成")
    
    # 激活虚拟环境并安装依赖
    if sys.platform == "win32":
        activate_script = venv_dir / "Scripts" / "activate.bat"
        pip_cmd = venv_dir / "Scripts" / "pip.exe"
    else:
        activate_script = venv_dir / "bin" / "activate"
        pip_cmd = venv_dir / "bin" / "pip"
    
    # 检查依赖是否已安装
    try:
        import uvicorn
        print_success("依赖已安装")
    except ImportError:
        print_info("安装依赖...")
        subprocess.run([str(pip_cmd), "install", "-r", "requirements.txt"], check=True)
        print_success("依赖安装完成")
    
    # 启动后端
    print_info("启动 FastAPI 服务器...")
    print_info("后端地址: http://localhost:8001")
    print_info("API 文档: http://localhost:8001/docs")
    
    if sys.platform == "win32":
        # Windows 下使用 python -m uvicorn
        cmd = [
            sys.executable, "-m", "uvicorn",
            "src.api.main:app",
            "--reload",
            "--port", "8001",
            "--host", "0.0.0.0"
        ]
    else:
        # Unix 下使用 uvicorn 命令
        cmd = [
            "uvicorn",
            "src.api.main:app",
            "--reload",
            "--port", "8001",
            "--host", "0.0.0.0"
        ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print_info("后端服务已停止")
    except Exception as e:
        print_error(f"启动后端失败: {e}")
        sys.exit(1)

def start_frontend():
    """启动前端服务"""
    print_header("启动前端服务")
    
    os.chdir(FRONTEND_DIR)
    
    # 检查 node_modules
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print_info("安装前端依赖...")
        subprocess.run(["npm", "install"], check=True)
        print_success("前端依赖安装完成")
    
    # 启动前端
    print_info("启动 Next.js 开发服务器...")
    print_info("前端地址: http://localhost:3000")
    
    try:
        subprocess.run(["npm", "run", "dev"], check=True)
    except KeyboardInterrupt:
        print_info("前端服务已停止")
    except Exception as e:
        print_error(f"启动前端失败: {e}")
        sys.exit(1)

def main():
    """主函数"""
    print_header("GradeOS Platform 开发环境启动")
    
    # 检查环境
    check_python_version()
    check_node_version()
    check_backend_env()
    check_frontend_env()
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        service = sys.argv[1].lower()
        if service == "backend":
            start_backend()
        elif service == "frontend":
            start_frontend()
        elif service == "all":
            # 同时启动后端和前端（需要两个终端）
            print_info("请在两个不同的终端中运行以下命令:")
            print(f"  终端1: python start_dev.py backend")
            print(f"  终端2: python start_dev.py frontend")
        else:
            print_error(f"未知的服务: {service}")
            print_info("用法: python start_dev.py [backend|frontend|all]")
            sys.exit(1)
    else:
        # 默认启动后端
        print_info("默认启动后端服务")
        print_info("用法: python start_dev.py [backend|frontend|all]")
        start_backend()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_info("\n开发环境已停止")
        sys.exit(0)
    except Exception as e:
        print_error(f"发生错误: {e}")
        sys.exit(1)
