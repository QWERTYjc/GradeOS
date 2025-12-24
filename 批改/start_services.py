"""启动所有服务（API + Worker）

使用方法：
    python start_services.py
    
    # 或指定 Worker 数量
    python start_services.py --workers 3
"""

import subprocess
import sys
import os
import signal
import time
import argparse
from typing import List


def main():
    parser = argparse.ArgumentParser(description="启动 AI 批改系统服务")
    parser.add_argument("--port", type=int, default=8002, help="API 端口")
    parser.add_argument("--workers", type=int, default=1, help="Worker 进程数")
    parser.add_argument("--concurrency", type=int, default=5, help="每个 Worker 的并发数")
    args = parser.parse_args()
    
    processes: List[subprocess.Popen] = []
    
    # 设置环境变量
    env = os.environ.copy()
    env["WORKER_CONCURRENCY"] = str(args.concurrency)
    
    try:
        print("=" * 60)
        print("AI 批改系统启动")
        print("=" * 60)
        
        # 启动 API 服务
        print(f"\n[1] 启动 API 服务 (端口 {args.port})...")
        api_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.api.main:app", 
             "--port", str(args.port), "--host", "0.0.0.0"],
            env=env
        )
        processes.append(api_process)
        print(f"    API PID: {api_process.pid}")
        
        # 等待 API 启动
        time.sleep(2)
        
        # 启动 Worker 进程
        print(f"\n[2] 启动 {args.workers} 个 Worker 进程...")
        for i in range(args.workers):
            worker_process = subprocess.Popen(
                [sys.executable, "-m", "src.workers.queue_worker"],
                env=env
            )
            processes.append(worker_process)
            print(f"    Worker {i+1} PID: {worker_process.pid}")
        
        print("\n" + "=" * 60)
        print("所有服务已启动！")
        print(f"API: http://localhost:{args.port}")
        print(f"Worker 进程数: {args.workers}")
        print("按 Ctrl+C 停止所有服务")
        print("=" * 60)
        
        # 等待进程
        while True:
            # 检查进程状态
            for p in processes:
                if p.poll() is not None:
                    print(f"\n警告: 进程 {p.pid} 已退出 (code={p.returncode})")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n收到停止信号，正在关闭所有服务...")
        
    finally:
        # 停止所有进程
        for p in processes:
            if p.poll() is None:
                print(f"停止进程 {p.pid}...")
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
        
        print("所有服务已停止")


if __name__ == "__main__":
    main()
