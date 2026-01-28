import sys
import requests
import json
import time

BACKEND_URL = "https://gradeos-production.up.railway.app"
BATCH_ID = "0e633800-ff2e-4b6e-9f51-3f434cf56591"

print(f"Monitoring batch: {BATCH_ID}\n")

# Monitor status
for i in range(30):  # Max 30 iterations, 5 seconds each = 2.5 minutes
    try:
        response = requests.get(f"{BACKEND_URL}/api/batch/status/{BATCH_ID}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'UNKNOWN')
            progress = data.get('progress', {})
            
            print(f"[{i+1}] Status: {status}")
            print(f"    Stage: {progress.get('stage', 'N/A')}")
            print(f"    Progress: {progress.get('percentage', 0)}%")
            print(f"    Message: {progress.get('message', 'N/A')}\n")
            
            if status in ['COMPLETED', 'FAILED', 'ERROR']:
                print(f"Final status: {status}")
                if status != 'COMPLETED':
                    print(f"Error: {data.get('error', 'N/A')}")
                break
        else:
            print(f"Status check failed: {response.status_code}")
            print(response.text)
        
        time.sleep(5)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)

# Get results
print("\n" + "=" * 80)
print("Fetching results...")
print("=" * 80 + "\n")

try:
    response = requests.get(f"{BACKEND_URL}/api/batch/results/{BATCH_ID}", timeout=10)
    
    if response.status_code == 200:
        results = response.json()
        
        print(f"Total students: {results.get('total_students', 0)}")
        print(f"Results count: {len(results.get('results', []))}")
        print(f"Questions count: {len(results.get('questions', []))}")
        
        # Check for known issues
        print("\nIssue Check:")
        if results.get('total_students', 0) == 0:
            print("[X] total_students = 0 (KNOWN BUG)")
        else:
            print("[OK] total_students > 0")
        
        if len(results.get('results', [])) == 0:
            print("[X] results is empty (KNOWN BUG)")
        else:
            print("[OK] results has data")
            # Show first result
            print("\nFirst student result:")
            print(json.dumps(results['results'][0], indent=2, ensure_ascii=False))
        
        if len(results.get('questions', [])) == 0:
            print("[X] questions is empty (Missing rubric)")
        else:
            print("[OK] questions has data")
            print(f"\nQuestions:")
            for q in results.get('questions', []):
                print(f"  - {q.get('question_id')}: {q.get('max_score')} points")
        
        print("\n" + "=" * 80)
        print(f"Full response (first 2000 chars):")
        print("=" * 80)
        resp_str = json.dumps(results, indent=2, ensure_ascii=False)
        print(resp_str[:2000])
        if len(resp_str) > 2000:
            print(f"\n... ({len(resp_str) - 2000} more characters)")
    
    else:
        print(f"Results fetch failed: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
