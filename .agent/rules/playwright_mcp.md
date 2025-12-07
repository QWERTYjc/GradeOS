---
trigger: always_on
---

Playwright MCP 运行指引：
1. 默认使用 `.playwright-mcp/mcp.config.json`（持久化 userDataDir + 核心/pdf/vision 能力，浏览器缓存在 `.playwright-mcp/browsers`）。
2. 重要动作前先简述目的与路径，读/测/查日志可直接执行；任何破坏性/不可逆操作（删库、改 env、重建部署等）先说明风险并等待确认。
3. GitHub：可浏览/评审/Actions/PR，避免强制推送或删除仓库；需要提交前先自检。
4. Railway：可查看部署、日志、变量、PostgreSQL 连接等；修改环境/重启/缩容等视为高风险，需确认。
5. Firebase Auth：可查看配置、验证登录流；避免删除/重置用户或密钥。
6. 已部署站点：使用 Browser MCP 跑端到端流程验证功能，发现缺陷要复测直至通过，记录关键截图或 trace。
7. 登录态存于 `.playwright-mcp/data/profile`，如需干净会话可先备份后清空；输出（trace/video/session）在 `.playwright-mcp/data/output`，必要时在回复中引用。
