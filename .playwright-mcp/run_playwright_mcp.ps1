# Quick launcher for Playwright MCP on Windows.
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $root "browsers"

if (-not (Test-Path $env:PLAYWRIGHT_BROWSERS_PATH)) {
  New-Item -ItemType Directory -Force -Path $env:PLAYWRIGHT_BROWSERS_PATH | Out-Null
}

Push-Location $root
try {
  npx --prefix $root mcp-server-playwright --config (Join-Path $root "mcp.config.json") @ExtraArgs
} finally {
  Pop-Location
}
