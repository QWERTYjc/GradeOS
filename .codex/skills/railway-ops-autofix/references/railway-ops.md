# Railway Ops Quick Reference

## CLI basics

- `railway status` : show current linked project/service/environment.
- `railway link` : link the repo to a Railway project.
- `railway service` : select or link a service.
- `railway environment` : select or link an environment.
- `railway open` : open the current project in the browser.

## Logs

- `railway logs` : latest logs for the current project/service.
- `railway logs -d` : deployment logs.
- `railway logs -b` : build logs.
- `railway logs --json` : JSON output when machine parsing is needed.

## Variables and redeploy

- `railway variables --set "KEY=VALUE"` : set env var. Add `-s <service>` and/or `-e <environment>` as needed.
- `railway redeploy -s <service>` : redeploy the latest deployment for a service.

## Web console

- Build/Deploy panel: open a specific deployment to view logs.
- Observability > Log Explorer: filter and monitor logs across the environment.

## Cache disable

- Set `NO_CACHE=1` to disable build cache for a service, redeploy, then remove `NO_CACHE` after success.
