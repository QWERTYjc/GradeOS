import sys
import requests
from pathlib import Path

print("Script started", file=sys.stderr)
sys.stderr.flush()

BACKEND_URL = "https://gradeos-production.up.railway.app"

try:
    print("Testing backend health...", file=sys.stderr)
    sys.stderr.flush()
    
    response = requests.get(f"{BACKEND_URL}/api/health", timeout=10)
    print(f"Health check status: {response.status_code}", file=sys.stderr)
    print(response.json())
    
    print("\nPreparing PDF file...", file=sys.stderr)
    sys.stderr.flush()
    
    pdf_path = Path("temp/gradeos_test_batch_30.pdf")
    if not pdf_path.exists():
        print(f"ERROR: PDF not found at {pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"PDF found: {pdf_path.stat().st_size} bytes", file=sys.stderr)
    sys.stderr.flush()
    
    print("\nSubmitting batch job...", file=sys.stderr)
    sys.stderr.flush()
    
    files = {
        'files': ('test.pdf', open(pdf_path, 'rb'), 'application/pdf')
    }
    
    data = {
        'exam_id': 'test_001',
        'teacher_id': 'teacher_001'
    }
    
    response = requests.post(f"{BACKEND_URL}/api/batch/submit", files=files, data=data, timeout=60)
    print(f"Submit status: {response.status_code}", file=sys.stderr)
    sys.stderr.flush()
    
    if response.status_code == 200:
        result = response.json()
        print("SUCCESS!")
        print(f"Batch ID: {result.get('batch_id')}")
        print(f"Response: {result}")
    else:
        print(f"ERROR: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Exception: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)

print("Script ended", file=sys.stderr)
