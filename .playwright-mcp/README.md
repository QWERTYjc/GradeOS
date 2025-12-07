# Playwright MCP 配置说明

- 依赖：Node.js 18+。本目录已安装 `@playwright/mcp@0.0.48`，浏览器缓存固定在 `.playwright-mcp/browsers`（通过 `PLAYWRIGHT_BROWSERS_PATH`）。
- 核心配置：`mcp.config.json` 使用 Chromium、持久化用户目录 `./data/profile`（便于 GitHub/Railway/Firebase 登录复用）、启用 `core/pdf/vision` 能力、共享上下文、操作/导航超时 8s/90s，并把 session/trace/video 写入 `./data/output`。
- 运行方式：
  - PowerShell 快捷脚本（可追加原生 CLI 参数）：`powershell -ExecutionPolicy Bypass -File .playwright-mcp/run_playwright_mcp.ps1 -- --headless`（默认 headless，传 `--headful` 可开可视）。
  - npm 脚本：`cd .playwright-mcp && npm run mcp`（headless）或 `npm run mcp:headful`。
  - 直接命令：`npx --prefix .playwright-mcp mcp-server-playwright --config .playwright-mcp/mcp.config.json`。
- MCP 客户端示例（按需替换绝对路径）：
  - Codex `config.toml` 片段：
    ```toml
    [mcp_servers.playwright]
    command = "npx"
    args = ["--prefix", "D:/project/aiguru/.playwright-mcp", "mcp-server-playwright", "--config", "D:/project/aiguru/.playwright-mcp/mcp.config.json"]
    ```
  - Cursor/VS Code：命令同上，可在 MCP 设置中填写。
- 操作守则：
  - 默认允许用 Browser MCP 测试/操控 GitHub、Railway、Firebase Auth、已部署站点；登录态保存在 `./data/profile`，如需重置删除该目录。
  - 破坏性动作（删库、改环境变量、重启/重建部署等）先在回复中写明风险并等待确认；读/测/查日志可直接执行。
  - 运行后 trace/video/session 会落在 `./data/output` 便于复盘；需要上传的文件统一放到 `uploads/` 或在回复中说明路径。
