"""测试学生助手 API"""
import requests
import json

url = "http://localhost:8001/api/assistant/chat"
payload = {
    "student_id": "s-001",  # 使用真实的学生 ID
    "message": "请帮我深究这道错题 Q1，我得了 2/5 分。",
    "session_mode": "wrong_question_review",
    "wrong_question_context": {
        "questionId": "1",
        "score": 2,
        "maxScore": 5,
        "feedback": "计算错误"
    }
}

print(f"Sending request to {url}")
print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")

try:
    response = requests.post(url, json=payload, timeout=120)
    print(f"\nStatus: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
except Exception as e:
    print(f"Error: {e}")
