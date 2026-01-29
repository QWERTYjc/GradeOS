---
name: railway-ops-autofix
description: "Operate Railway for the GradeOS project via CLI and web console (browser MCP): monitor logs, detect deploy/build/runtime errors, update environment variables, clear build cache, and redeploy. Use when the user asks to watch Railway logs, fix Railway deployment failures, or perform Railway console operations for GradeOS."
---

# Railway Ops Autofix

## Overview

Monitor the GradeOS Railway project via CLI and the web console, detect errors, and apply fast fixes that are explicitly allowed (env var changes and cache clears), then verify recovery.

## Workflow Decision Tree

### 0) Scope & safety

- Target project is **GradeOS**. Default environment is **production** unless the user states otherwise.
- If the environment or service is unclear, ask once; otherwise pick the most recently failing service in logs.
- Allowed without confirmation: update env vars, clear build cache, redeploy.
- Anything destructive or structural (delete services/envs/volumes, scale to zero, change plans, remove domains) requires explicit user confirmation.

### 1) Connect & open project

- CLI: confirm context with `railway status`. If unlinked, run `railway link` and select GradeOS.
- If needed, link a specific service or environment via `railway service` and `railway environment`.
- Web console: open the project dashboard (use `railway open` or direct navigation) and select GradeOS.
- If any login or 2FA prompt appears, stop and ask the user to complete it.

### 2) Monitor logs (CLI + web)

- CLI: use `railway logs` to view the latest deployment logs. Use `-d` for deployment logs and `-b` for build logs; `--json` if you need machine parsing.
- Web console:
  - Build/Deploy panel for a specific deployment's logs.
  - Observability > Log Explorer for environment-wide logs and filters.
- Keep the web log stream open for real-time monitoring; use the CLI for quick snapshots after each fix.

### 3) Detect errors

- Look for crash loops, build failures, missing env vars, or connection errors.
- Optional classifier: pipe log text into `scripts/scan_logs.py` for a fast pattern match, e.g. `railway logs | python scripts/scan_logs.py`.
- If the error is unclear, capture:
  - Service + environment
  - Deployment/build ID
  - Timestamp and 20-50 lines around the error
  - Recent config changes (if any)

### 4) Fix actions (auto)

- **Missing env var**: set it via CLI (`railway variables --set "KEY=VALUE"`, add `-s`/`-e` if needed) or via the Variables UI, then redeploy if required.
- **Clear build cache**: set `NO_CACHE=1` for the service, redeploy, then remove `NO_CACHE` after a successful build.
- **Redeploy**: use `railway redeploy -s <SERVICE>` or the Deployments UI to re-run the latest deployment.
- Keep fixes minimal: only env vars or cache changes are allowed without user confirmation.

### 5) Verify & iterate

- Re-check logs immediately after redeploy and again after the service has been up for a few minutes.
- If the same error persists, gather fresh context and apply the next likely fix.
- If a fix would require destructive changes or plan changes, ask the user first.

## Resources

### scripts/

- `scripts/scan_logs.py`: lightweight log classifier (stdin or file input) to highlight common error types.

### references/

- `references/railway-ops.md`: CLI + web console actions for logs, variables, and redeploys.
- `references/error-patterns.md`: common log signatures mapped to the safest next action.
