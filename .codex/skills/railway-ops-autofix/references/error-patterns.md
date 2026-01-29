# Error Patterns -> Safe First Actions

Use these as fast hints only. If the error is ambiguous, capture context and ask the user.

## Missing environment variables

**Symptoms**
- "Missing environment variable"
- "process.env.<NAME> is undefined"
- "<NAME> is not set"

**First action**
- Set the missing variable via CLI or the Variables UI, then redeploy.

## Build failures

**Symptoms**
- "build failed"
- "npm ERR!" / "yarn error" / "pnpm ERR!"
- non-zero exit code during build

**First action**
- Check recent changes. If cache suspicion exists, set `NO_CACHE=1` and redeploy.

## Crash loop or immediate exit

**Symptoms**
- "Exited with code ..." repeatedly
- "CrashLoop" or "restart" loops

**First action**
- Check runtime logs for missing env vars or connection errors. Adjust env vars if needed.

## Connection errors

**Symptoms**
- "ECONNREFUSED" / "ENOTFOUND" / "EAI_AGAIN"
- "Connection refused" / "getaddrinfo" errors

**First action**
- Verify host, port, and credentials env vars. If secrets changed, update and redeploy.

## Out-of-memory (OOM)

**Symptoms**
- "JavaScript heap out of memory"
- "Killed" / "Exit code 137"

**First action**
- Reduce memory pressure in config or ask user to approve plan/size changes.

## Migration/schema errors

**Symptoms**
- "prisma" / "sequelize" migration failures
- "relation does not exist"

**First action**
- Verify DB connection vars and migration configuration. Ask before running destructive migrations.
