import requests
import os

# Create minimal valid PDF files
pdf_header = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer
<< /Size 4 /Root 1 0 R >>
startxref
203
%%EOF"""

with open("test_rubric.pdf", "wb") as f:
    f.write(pdf_header)
with open("test_exam.pdf", "wb") as f:
    f.write(pdf_header)

# Correct URL - batch router has no /api/v1 prefix
url = "http://localhost:8001/batch/submit"

files = [
    ('files', ('test_exam.pdf', open('test_exam.pdf', 'rb'), 'application/pdf')),
    ('rubrics', ('test_rubric.pdf', open('test_rubric.pdf', 'rb'), 'application/pdf'))
]

data = {
    'exam_id': 'test_exam_123'
}

try:
    print(f"Uploading to {url}...")
    response = requests.post(url, files=files, data=data, timeout=30)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("Upload SUCCESS!")
    else:
        print("Upload FAILED.")
except Exception as e:
    print(f"Error: {e}")
finally:
    # Clean up
    try:
        os.remove("test_rubric.pdf")
        os.remove("test_exam.pdf")
    except:
        pass
