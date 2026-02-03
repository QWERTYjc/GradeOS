"""测试登录 API"""
import requests
import json

url = "http://localhost:8001/api/auth/login"
payload = {
    "username": "student",
    "password": "123456"
}

print(f"Sending login request to {url}")

try:
    response = requests.post(url, json=payload, timeout=30)
    print(f"\nStatus: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
except Exception as e:
    print(f"Error: {e}")
