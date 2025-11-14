# AI批改系统 - 部署指南

## 本地开发环境

### 快速开始

1. **克隆项目**
```bash
git clone <repository-url>
cd ai_correction
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
# 复制配置文件
copy .env.local .env

# 编辑配置
OPENAI_API_KEY=your-key-here
```

4. **初始化数据库**
```bash
python local_runner.py
```

5. **启动应用**
```bash
# Windows
start_local.bat

# 或手动启动
streamlit run main.py
```

## 生产环境部署

### Railway部署（推荐）

#### 前置要求
- Railway账号
- GitHub仓库
- PostgreSQL数据库

#### 部署步骤

1. **连接GitHub仓库**
   - 登录Railway
   - 创建新项目
   - 连接GitHub仓库

2. **配置环境变量**
```bash
DATABASE_URL=<railway-postgres-url>
OPENAI_API_KEY=<your-key>
ENVIRONMENT=production
DEFAULT_MODE=professional
```

3. **配置构建命令**
```bash
# Railway自动检测requirements.txt
# 如需自定义：
pip install -r requirements.txt
```

4. **配置启动命令**
```bash
streamlit run main.py --server.port=$PORT
```

5. **数据库迁移**
```bash
python functions/database/migration.py upgrade
```

### Docker部署

#### Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501"]
```

#### docker-compose.yml

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8501:8501"
    environment:
      - DATABASE_URL=sqlite:///ai_correction.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
```

#### 启动

```bash
docker-compose up -d
```

### Vercel部署

#### vercel.json

```json
{
  "buildCommand": "pip install -r requirements.txt",
  "devCommand": "streamlit run main.py",
  "installCommand": "pip install -r requirements.txt"
}
```

## 数据库配置

### SQLite（开发）

```bash
DATABASE_URL=sqlite:///ai_correction.db
```

### PostgreSQL（生产）

```bash
DATABASE_URL=postgresql://user:password@host:5432/database
```

### 数据库迁移

```bash
# 创建迁移
python functions/database/migration.py create -m "描述"

# 执行升级
python functions/database/migration.py upgrade

# 查看当前版本
python functions/database/migration.py current
```

## 性能优化

### 1. 并行处理配置

```bash
# .env
MAX_PARALLEL_WORKERS=10  # 根据服务器核心数调整
```

### 2. Token阈值优化

```bash
EFFICIENT_MODE_THRESHOLD=6000
PROFESSIONAL_MODE_THRESHOLD=4000
```

### 3. 缓存配置

使用Redis缓存（可选）：
```bash
REDIS_URL=redis://localhost:6379
```

## 监控和日志

### 日志配置

```bash
LOG_LEVEL=INFO
LOG_FILE=logs/ai_correction.log
```

### 监控指标

- Token消耗量
- 处理时间
- 错误率
- 并发任务数

## 安全配置

### 1. API Key安全

```bash
# 使用环境变量
OPENAI_API_KEY=<存储在安全位置>

# 不要提交到git
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore
```

### 2. 数据库连接

```bash
# 使用连接池
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
```

### 3. Firebase认证（可选）

```bash
FIREBASE_PROJECT_ID=your-project
FIREBASE_PRIVATE_KEY=<从安全存储获取>
```

## 备份和恢复

### 数据库备份

```bash
# SQLite
cp ai_correction.db ai_correction.db.backup

# PostgreSQL
pg_dump database_name > backup.sql
```

### 恢复

```bash
# SQLite
cp ai_correction.db.backup ai_correction.db

# PostgreSQL
psql database_name < backup.sql
```

## 故障排除

### 常见问题

1. **依赖安装失败**
```bash
pip install -r requirements.txt --upgrade
```

2. **数据库连接失败**
```bash
# 检查连接字符串
python -c "from config.railway_postgres import get_railway_config; config.test_connection()"
```

3. **内存不足**
```bash
# 减少并行worker数
MAX_PARALLEL_WORKERS=4
```

## 扩展性

### 水平扩展

- 使用负载均衡器
- 部署多个应用实例
- 共享PostgreSQL数据库

### 垂直扩展

- 增加服务器CPU核心数
- 增加内存
- 使用SSD存储

## 维护

### 定期任务

1. 清理旧日志
2. 数据库优化
3. 依赖更新
4. 安全补丁

### 更新流程

```bash
# 1. 备份
# 2. 拉取新代码
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 数据库迁移
python functions/database/migration.py upgrade

# 5. 重启应用
```
