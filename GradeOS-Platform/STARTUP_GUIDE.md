# GradeOS Platform 启动指南

## 快速启动

### 方式1: 使用 Python 脚本（推荐）

#### 启动后端
```bash
cd GradeOS-Platform/backend
python run.py
```

或指定端口：
```bash
python run.py --port 8001
```

#### 启动前端
```bash
cd GradeOS-Platform/frontend
npm run dev
```

#### 同时启动后端和前端
在两个不同的终端中分别运行：

**终端1 - 后端**:
```bash
cd GradeOS-Platform/backend
python run.py
```

**终端2 - 前端**:
```bash
cd GradeOS-Platform/frontend
npm run dev
```

### 方式2: 使用综合启动脚本

从项目根目录运行：

```bash
# 启动后端
python start_dev.py backend

# 启动前端
python start_dev.py frontend

# 显示启动说明
python start_dev.py all
```

### 方式3: 使用 PowerShell 脚本（Windows）

```powershell
.\start_dev.ps1
```

### 方式4: 使用 Docker

```bash
docker-compose up -d
```

---

## 环境配置

### 后端环境变量

创建 `GradeOS-Platform/backend/.env` 文件：

```env
# Gemini API 配置
GEMINI_API_KEY=your_api_key_here

# 数据库配置（可选，无数据库模式下不需要）
DATABASE_URL=postgresql://user:password@localhost:5432/gradeos
REDIS_URL=redis://localhost:6379

# JWT 配置
JWT_SECRET=your_secret_key_here

# 部署模式
DEPLOYMENT_MODE=no_database  # 或 database
```

### 前端环境变量

创建 `GradeOS-Platform/frontend/.env.local` 文件：

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8001
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8001
```

---

## 服务地址

启动后，可以访问以下地址：

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3000 | Next.js 应用 |
| 后端 API | http://localhost:8001 | FastAPI 服务 |
| API 文档 | http://localhost:8001/docs | Swagger UI |
| ReDoc | http://localhost:8001/redoc | ReDoc 文档 |

---

## 常见问题

### Q: 后端启动失败，提示 "ModuleNotFoundError"

**A**: 需要安装依赖
```bash
cd GradeOS-Platform/backend
pip install -r requirements.txt
```

或使用 uv：
```bash
uv sync
```

### Q: 前端启动失败，提示 "npm: command not found"

**A**: 需要安装 Node.js，访问 https://nodejs.org/

### Q: 后端启动成功但无法访问 API

**A**: 检查防火墙设置，确保 8001 端口未被占用
```bash
# Windows
netstat -ano | findstr :8001

# Linux/Mac
lsof -i :8001
```

### Q: 前端无法连接到后端

**A**: 检查 `.env.local` 中的 API 地址配置是否正确

### Q: 如何在不同端口启动服务？

**A**: 使用命令行参数
```bash
# 后端使用 8002 端口
python run.py --port 8002

# 前端使用 3001 端口
PORT=3001 npm run dev
```

---

## 开发工作流

### 1. 启动服务
```bash
# 终端1 - 后端
cd GradeOS-Platform/backend
python run.py

# 终端2 - 前端
cd GradeOS-Platform/frontend
npm run dev
```

### 2. 访问应用
打开浏览器访问 http://localhost:3000

### 3. 进行开发
- 后端代码修改会自动重载（--reload 模式）
- 前端代码修改会自动刷新

### 4. 查看日志
- 后端日志在终端1 显示
- 前端日志在终端2 显示
- 浏览器控制台显示前端错误

---

## 生产部署

### 使用 Docker Compose

```bash
docker-compose up -d
```

### 手动部署

**后端**:
```bash
cd GradeOS-Platform/backend
pip install -r requirements.txt
gunicorn -w 4 -b 0.0.0.0:8001 src.api.main:app
```

**前端**:
```bash
cd GradeOS-Platform/frontend
npm install
npm run build
npm run start
```

---

## 性能优化

### 后端优化
- 使用 `--no-reload` 禁用自动重载
- 增加 worker 数量：`gunicorn -w 8`
- 启用缓存：配置 Redis

### 前端优化
- 使用 `npm run build` 生成优化版本
- 启用 CDN 加速
- 配置 gzip 压缩

---

## 故障排查

### 检查服务状态

```bash
# 检查后端
curl http://localhost:8001/docs

# 检查前端
curl http://localhost:3000
```

### 查看详细日志

**后端**:
```bash
python run.py  # 日志直接输出到终端
```

**前端**:
```bash
npm run dev  # 日志直接输出到终端
```

### 重置环境

```bash
# 清除后端缓存
rm -rf GradeOS-Platform/backend/__pycache__
rm -rf GradeOS-Platform/backend/.pytest_cache

# 清除前端缓存
rm -rf GradeOS-Platform/frontend/.next
rm -rf GradeOS-Platform/frontend/node_modules
npm install
```

---

## 更多信息

- [后端 README](./GradeOS-Platform/backend/README.md)
- [前端 README](./GradeOS-Platform/frontend/README.md)
- [API 文档](./GradeOS-Platform/backend/docs/)
- [项目结构](./GradeOS-Platform/README.md)

---

**最后更新**: 2025-12-28
