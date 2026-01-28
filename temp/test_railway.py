"""测试 Railway 部署的后端 API"""
import requests
import json

BACKEND_URL = "https://gradeos-production.up.railway.app"

def test_health():
    """测试健康检查端点"""
    try:
        print("[INFO] 测试健康检查端点...")
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("[OK] 健康检查成功")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return True
        else:
            print(f"[ERROR] 健康检查失败: {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] 请求失败: {str(e)}")
        return False

def test_api_docs():
    """测试 API 文档端点"""
    try:
        print("\n[INFO] 测试 API 文档端点...")
        response = requests.get(f"{BACKEND_URL}/docs", timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print("[OK] API 文档可访问")
            return True
        else:
            print("[ERROR] API 文档不可访问")
            return False
    except Exception as e:
        print(f"[ERROR] 请求失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Railway 部署验证测试")
    print("=" * 60)
    
    # 测试健康检查
    health_ok = test_health()
    
    # 测试 API 文档
    docs_ok = test_api_docs()
    
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"健康检查: {'[OK] 通过' if health_ok else '[ERROR] 失败'}")
    print(f"API 文档: {'[OK] 通过' if docs_ok else '[ERROR] 失败'}")
