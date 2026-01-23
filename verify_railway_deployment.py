#!/usr/bin/env python3
"""
Railway 部署验证脚本

用于验证 Railway 部署的后端服务是否正常运行
"""

import sys
import requests
from typing import Dict, Any


def test_health_endpoint(base_url: str) -> Dict[str, Any]:
    """测试健康检查端点"""
    url = f"{base_url}/api/health"
    print(f"测试健康检查: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print("✅ 健康检查成功!")
        print(f"   状态: {data.get('status')}")
        print(f"   服务: {data.get('service')}")
        print(f"   版本: {data.get('version')}")
        print(f"   部署模式: {data.get('deployment_mode')}")
        print(f"   功能: {data.get('features')}")
        
        return {"success": True, "data": data}
    except requests.exceptions.RequestException as e:
        print(f"❌ 健康检查失败: {e}")
        return {"success": False, "error": str(e)}


def test_root_endpoint(base_url: str) -> Dict[str, Any]:
    """测试根端点"""
    url = base_url
    print(f"\n测试根端点: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print("✅ 根端点成功!")
        print(f"   消息: {data.get('message')}")
        
        return {"success": True, "data": data}
    except requests.exceptions.RequestException as e:
        print(f"❌ 根端点失败: {e}")
        return {"success": False, "error": str(e)}


def main():
    """主函数"""
    if len(sys.argv) > 1:
        base_url = sys.argv[1].rstrip('/')
    else:
        # 默认使用 Railway 部署地址
        base_url = "https://gradeos-production.up.railway.app"
    
    print("=" * 60)
    print("Railway 部署验证")
    print("=" * 60)
    print(f"后端地址: {base_url}\n")
    
    # 运行测试
    results = []
    results.append(test_health_endpoint(base_url))
    results.append(test_root_endpoint(base_url))
    
    # 总结
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    
    if success_count == total_count:
        print(f"✅ 所有测试通过 ({success_count}/{total_count})")
        print("\n后端服务正常运行！")
        print("\n下一步:")
        print("1. 在 Railway 控制台配置环境变量")
        print("2. 配置前端的 NEXT_PUBLIC_API_URL")
        print("3. 重新部署并测试完整功能")
        sys.exit(0)
    else:
        print(f"❌ 部分测试失败 ({success_count}/{total_count})")
        print("\n请检查:")
        print("1. Railway 服务是否正在运行")
        print("2. 网络连接是否正常")
        print("3. 后端 URL 是否正确")
        sys.exit(1)


if __name__ == "__main__":
    main()
