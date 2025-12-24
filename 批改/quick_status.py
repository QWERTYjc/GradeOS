import requests
import json

batch_id = "eb27f893-8dd4-4958-be56-3dfd97df542e"
response = requests.get(f'http://localhost:8001/batch/status/{batch_id}')
print(f"状态码: {response.status_code}")
if response.status_code == 200:
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
else:
    print(response.text)
