# Railway 部署指南

本指南将帮助你在 Railway 上部署 AI 批改系统，包括 PostgreSQL 和 Redis。

## 前置条件

- Railway 账号（https://railway.app）
- GitHub 账号（用于连接代码仓库）
- Gemini API Key

## 部署步骤

### 1. 创建 Railway 项目

1. 访问 https://railway.app/new
2. 点击 "Deploy from GitHub repo"
3. 选择你的代码仓库
4. Railway 会自动检测项目并创建服务

### 2. 添加 PostgreSQL 数据库

1. 在项目页面，点击 "+ New"
2. 选择 "Database" → "Add PostgreSQL"
3. Railway 会自动创建数据库并生成连接字符串
4. 数据库变量会自动注入到环境变量 `DATABASE_URL`

### 3. 添加 Redis

1. 在项目页面，点击 "+ New"
2. 选择 "Database" → "Add Redis"
3. Railway 会自动创建 Redis 实例
4. Redis 连接字符串会注入到环境变量 `REDIS_URL`

### 4. 配置环境变量

在你的服务设置中，添加以下环境变量：

```bash
# Gemini API Key（必需）
GEMINI_API_KEY=your_gemini_api_key_here

# 关闭离线模式
OFFLINE_MODE=false

# Worker 配置
WORKER_CONCURRENCY=5
WORKER_POLL_INTERVAL=0.5

# 编排器模式
ORCHESTRATOR_MODE=langgraph
```

### 5. 配置启动命令

Railway 会自动使用 `Procfile` 或 `railway.toml` 中的启动命令：

```bash
python start_services.py --port $PORT --workers 2
```

### 6. 部署

1. 推送代码到 GitHub
2. Railway 会自动触发部署
3. 等待部署完成（约 3-5 分钟）

### 7. 运行数据库迁移

部署完成后，需要运行数据库迁移：

1. 在 Railway 项目页面，找到你的服务
2. 点击 "Settings" → "Deploy"
3. 在 "Custom Start Command" 中临时设置：
   ```bash
   alembic upgrade head && python start_services.py --port $PORT --workers 2
   ```
4. 或者使用 Railway CLI：
   ```bash
   railway run alembic upgrade head
   ```

## 架构说明

Railway 部署后的架构：

```
┌─────────────────────────────────────────┐
│           Railway Project               │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────┐  ┌──────────────┐   │
│  │  PostgreSQL  │  │    Redis     │   │
│  │   Database   │  │    Cache     │   │
│  └──────┬───────┘  └──────┬───────┘   │
│         │                  │           │
│         └────────┬─────────┘           │
│                  │                     │
│         ┌────────▼────────┐            │
│         │   API Service   │            │
│         │  (with Workers) │            │
│         │   Port: $PORT   │            │
│         └─────────────────┘            │
│                                         │
└─────────────────────────────────────────┘
```

## 监控和日志

### 查看日志

1. 在 Railway 项目页面，点击你的服务
2. 点击 "Deployments" 标签
3. 选择最新的部署，查看实时日志

### 监控指标

Railway 提供以下监控指标：
- CPU 使用率
- 内存使用率
- 网络流量
- 请求数量

## 成本估算

Railway 的定价（截至 2024）：

- **Hobby Plan**（免费）:
  - $5 免费额度/月
  - PostgreSQL: ~$5/月
  - Redis: ~$5/月
  - 应用服务: 按使用量计费

- **Pro Plan**（$20/月）:
  - $20 免费额度/月
  - 更高的资源限制
  - 优先支持

**预估成本**：
- 开发/测试环境：$0-10/月（使用免费额度）
- 生产环境：$20-50/月（取决于流量）

## 扩展配置

### 增加 Worker 数量

修改 `railway.toml` 或环境变量：

```bash
# 启动 4 个 Worker 进程
python start_services.py --port $PORT --workers 4 --concurrency 10
```

### 启用自动扩展

Railway 支持基于 CPU/内存的自动扩展：

1. 在服务设置中，找到 "Scaling"
2. 启用 "Autoscaling"
3. 设置最小和最大实例数

### 添加健康检查

在 `railway.toml` 中配置：

```toml
[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 100
```

确保在 API 中添加健康检查端点：

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

## 故障排查

### 常见问题

1. **数据库连接失败**
   - 检查 `DATABASE_URL` 环境变量是否正确
   - 确保数据库服务已启动

2. **Redis 连接失败**
   - 检查 `REDIS_URL` 环境变量
   - 确认 `OFFLINE_MODE=false`

3. **Worker 未启动**
   - 查看日志确认 Worker 进程是否启动
   - 检查 `WORKER_CONCURRENCY` 配置

4. **内存不足**
   - 减少 Worker 数量
   - 降低并发数
   - 升级到更高的 Railway 计划

### 调试命令

使用 Railway CLI 进行调试：

```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录
railway login

# 连接到项目
railway link

# 查看日志
railway logs

# 运行命令
railway run python -m src.workers.queue_worker

# 查看环境变量
railway variables
```

## 生产环境建议

1. **启用 HTTPS**：Railway 自动提供 HTTPS
2. **设置自定义域名**：在 Settings → Domains 中配置
3. **配置备份**：定期备份 PostgreSQL 数据
4. **监控告警**：集成 Sentry 或其他监控服务
5. **日志聚合**：使用 Datadog 或 LogDNA
6. **负载测试**：部署前进行压力测试

## 参考链接

- Railway 文档：https://docs.railway.app
- Railway CLI：https://docs.railway.app/develop/cli
- Railway 定价：https://railway.app/pricing
- 项目仓库：[你的 GitHub 仓库链接]
