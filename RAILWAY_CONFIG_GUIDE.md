# Railway 环境变量配置指南

> **重要**: 以下配置需要在 Railway 控制台中手动设置

---

## 第一步：配置后端环境变量

1. 访问 Railway 控制台: https://railway.app
2. 选择你的 GradeOS 后端项目
3. 点击 "Variables" 标签
4. 添加以下环境变量：

### 必需配置 ✅

```bash
# LLM API 配置 (必需)
LLM_API_KEY=<你的 OpenRouter API Key>
LLM_DEFAULT_MODEL=google/gemini-3-flash-preview
LLM_BASE_URL=https://openrouter.ai/api/v1

# 启用离线模式 (推荐 - 无需数据库即可运行)
OFFLINE_MODE=true
```

### 可选配置（如果你想使用完整功能）

```bash
# PostgreSQL 数据库
DATABASE_URL=<PostgreSQL 连接字符串>
# 格式示例: postgresql://user:password@host:port/database

# Redis 缓存
REDIS_URL=<Redis 连接字符串>
# 格式示例: redis://host:port
```

---

## 第二步：配置前端环境变量

1. 访问 Railway 控制台
2. 选择你的 GradeOS 前端项目
3. 点击 "Variables" 标签
4. 添加以下环境变量：

### 必需配置 ✅

```bash
# 后端 API 地址 (必需)
NEXT_PUBLIC_API_URL=https://gradeos-production.up.railway.app/api
```

**注意**: 请将 `gradeos-production.up.railway.app` 替换为你的实际后端域名。

**如何找到后端域名**:
- 在 Railway 后端项目的 "Settings" → "Domains" 中查看
- 或者在 "Deployments" 中查看最新部署的 URL

---

## 第三步：重新部署服务

配置完环境变量后，Railway 会自动触发重新部署。

### 验证部署

1. **后端健康检查**:
   ```bash
   curl https://your-backend-domain.railway.app/api/health
   ```
   应该返回:
   ```json
   {
     "status": "healthy",
     "service": "ai-grading-api",
     "version": "1.0.0",
     "deployment_mode": "offline",
     "features": {...}
   }
   ```

2. **前端访问测试**:
   - 打开前端 URL
   - 检查浏览器控制台 (F12 → Console)
   - 确认没有网络错误

---

## 常见问题

### Q: 我没有 OpenRouter API Key 怎么办？

A: 访问 https://openrouter.ai 注册账号并获取 API Key。

### Q: 必须配置数据库吗？

A: 不必须。设置 `OFFLINE_MODE=true` 后，系统会使用内存缓存运行，适合快速测试。

### Q: 如何添加 PostgreSQL 和 Redis？

A: 
1. 在 Railway 中点击 "New" → "Database"
2. 选择 PostgreSQL 或 Redis
3. Railway 会自动生成连接字符串
4. 将连接字符串添加到后端环境变量中

---

## 下一步

配置完成后：
1. 等待 Railway 重新部署完成（通常 2-5 分钟）
2. 访问前端 URL 测试登录功能
3. 尝试上传文件测试批改功能
4. 如有问题，查看 Railway 的 "Deployments" → "Logs"

---

## 联系支持

如果配置后仍有问题，请提供：
- Railway 部署日志截图
- 浏览器控制台错误截图
- 配置的环境变量列表（隐藏敏感信息）
