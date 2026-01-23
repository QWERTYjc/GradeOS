# 修复 Railway 部署登录界面 "Failed to fetch" 问题

## 问题分析
在 Railway 部署后，登录界面出现 "Failed to fetch" 错误，主要原因是前端代码中的 API 基础路径（`API_BASE`）在生产环境下回退到了 `http://localhost:8001/api`。
1. **硬编码回退**：`frontend/src/services/api.ts` 定义了 `const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';`。
2. **构建时注入失败**：Next.js 的 `NEXT_PUBLIC_` 变量在 `npm run build` 时注入。如果 Railway 构建阶段没有该环境变量，客户端代码将永远指向 localhost。
3. **网络不通**：用户的浏览器尝试访问自己电脑上的 `localhost:8001`，显然无法连接到 Railway 上的后端。

## 修复方案

### 1. 前端代码优化 (Code Fix)
修改 `api.ts` 和 `ws.ts`，使其在环境变量缺失时更智能地处理请求。
- 允许使用相对路径 `/api`（如果配置了代理或同源）。
- 增加容错逻辑，避免死板回退到 localhost。

### 2. Dockerfile 构建优化 (Build Fix)
修改 `frontend/Dockerfile` 以接收构建参数（Build Args），确保 Railway 的环境变量能传递到 `next build` 过程中。

### 3. 配置建议 (Configuration)
指导用户在 Railway 后台中正确配置环境变量。

## 待执行任务

- [ ] 修改 `frontend/src/services/api.ts`：实现动态 API 地址解析。
- [ ] 修改 `frontend/src/services/ws.ts`：同步优化 WebSocket 地址解析。
- [ ] 修改 `frontend/Dockerfile`：添加 `ARG NEXT_PUBLIC_API_URL` 支持。
- [ ] 验证代码更改。
