# API Key Setup

## Required Key
Set your Gemini key before starting the backend:

```bash
export LLM_API_KEY="your-gemini-api-key"
```

On Windows PowerShell:

```powershell
$env:LLM_API_KEY = "your-gemini-api-key"
```

## Optional Environment Variables
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/gradeos
REDIS_URL=redis://localhost:6379
```

## Verify
Start backend and check:

```bash
curl http://localhost:8001/health
```

If the key is invalid or missing, grading-related APIs will fail with authentication errors.
