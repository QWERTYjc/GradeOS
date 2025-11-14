# Railway平台部署指南

<cite>
**本文档引用的文件**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py)
- [ai_correction/main.py](file://ai_correction/main.py)
- [ai_correction/requirements.txt](file://ai_correction/requirements.txt)
- [ai_correction/config.py](file://ai_correction/config.py)
- [ai_correction/init_database.py](file://ai_correction/init_database.py)
- [ai_correction/functions/database/models.py](file://ai_correction/functions/database/models.py)
- [ai_correction/docs/DEPLOYMENT_GUIDE.md](file://ai_correction/docs/DEPLOYMENT_GUIDE.md)
- [ai_correction/docs/ENVIRONMENT_VARIABLES.md](file://ai_correction/docs/ENVIRONMENT_VARIABLES.md)
- [ai_correction/local_runner.py](file://ai_correction/local_runner.py)
- [ai_correction/start_local.bat](file://ai_correction/start_local.bat)
- [vercel.json](file://vercel.json)
</cite>

## 目录
1. [简介](#简介)
2. [项目架构概览](#项目架构概览)
3. [前置条件](#前置条件)
4. [环境变量配置](#环境变量配置)
5. [Railway部署流程](#railway部署流程)
6. [服务创建与配置](#服务创建与配置)
7. [数据库服务配置](#数据库服务配置)
8. [Redis缓存服务配置](#redis缓存服务配置)
9. [应用部署与启动](#应用部署与启动)
10. [部署状态验证](#部署状态验证)
11. [紧急修复流程](#紧急修复流程)
12. [故障排除指南](#故障排除指南)
13. [最佳实践建议](#最佳实践建议)

## 简介

本指南详细介绍了如何将AI智能批改系统部署到Railway平台。该系统采用多服务架构，包含Streamlit前端应用、PostgreSQL数据库和Redis缓存服务，支持高效的AI批改功能。

Railway是一个现代化的云平台，专为开发者提供简单易用的部署体验。本项目展示了如何利用Railway的自动化部署能力和丰富的服务生态系统来构建生产级应用。

## 项目架构概览

```mermaid
graph TB
subgraph "Railway平台"
subgraph "前端服务"
FE[Streamlit应用<br/>PORT=8000]
end
subgraph "后端服务"
BE[AI批改服务<br/>PORT=8000]
end
subgraph "数据库服务"
DB[(PostgreSQL<br/>Railway内置)]
end
subgraph "缓存服务"
REDIS[(Redis<br/>Railway内置)]
end
subgraph "外部服务"
LLM[OpenAI/Gemini API]
FB[Firebase认证]
end
end
FE --> BE
BE --> DB
BE --> REDIS
BE --> LLM
BE --> FB
```

**图表来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L48-L65)
- [ai_correction/main.py](file://ai_correction/main.py#L1-L50)

**章节来源**
- [ai_correction/docs/DEPLOYMENT_GUIDE.md](file://ai_correction/docs/DEPLOYMENT_GUIDE.md#L1-L50)
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L1-L112)

## 前置条件

### 必需工具和账户

1. **Railway账号**
   - 注册并登录 [Railway官网](https://railway.app)
   - 安装Railway CLI工具

2. **GitHub集成**
   - 创建GitHub账户
   - 将项目推送到GitHub仓库

3. **开发环境准备**
   - Python 3.9+
   - Git客户端
   - 命令行终端

### 项目准备

```bash
# 克隆项目
git clone <repository-url>
cd aiguru

# 安装依赖
pip install -r ai_correction/requirements.txt

# 验证本地运行
python ai_correction/local_runner.py
```

**章节来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L15-L30)
- [ai_correction/local_runner.py](file://ai_correction/local_runner.py#L1-L50)

## 环境变量配置

### 核心环境变量清单

| 变量名 | 描述 | 示例值 | 必需 |
|--------|------|--------|------|
| `DATABASE_URL` | PostgreSQL数据库连接字符串 | `postgresql://user:pass@host:5432/dbname` | 是 |
| `REDIS_URL` | Redis缓存服务连接字符串 | `redis://localhost:6379` | 是 |
| `SECRET_KEY` | 应用密钥 | `your-secret-key` | 是 |
| `PORT` | 应用监听端口 | `8000` | 是 |
| `ENVIRONMENT` | 运行环境 | `production` | 是 |
| `OPENAI_API_KEY` | OpenAI API密钥 | `sk-xxx` | 是 |
| `GEMINI_API_KEY` | Gemini API密钥 | `AIzaSyxxx` | 否 |

### 生产环境配置示例

```bash
# 数据库配置
DATABASE_URL=postgresql://postgres:sfraebGPmjkZtWpAsHqeHrxUrxuDSQFz@postgres.railway.internal:5432/railway

# Redis缓存配置
REDIS_URL=redis://default:fXZjFSKZfAfkTiqBfomlFHzcddmZZLLv@redis.railway.internal:6379

# 应用配置
SECRET_KEY=aiguru2-production-secret-key-2024
PORT=8000
ENVIRONMENT=production

# LLM配置
OPENAI_API_KEY=${OPENAI_API_KEY}
GEMINI_API_KEY=${GEMINI_API_KEY}

# 其他配置
DEFAULT_MODE=professional
MAX_PARALLEL_WORKERS=8
```

### 安全配置建议

1. **API密钥管理**
   - 使用环境变量而非硬编码
   - 在Railway控制台的安全选项中设置密钥
   - 定期轮换API密钥

2. **数据库连接**
   - 使用强密码
   - 启用SSL连接
   - 限制数据库访问IP

3. **密钥轮换**
   ```bash
   # 生成新密钥
   python -c "import secrets; print(secrets.token_hex(32))"
   
   # 更新环境变量
   railway variables set SECRET_KEY=new-generated-key
   ```

**章节来源**
- [ai_correction/docs/ENVIRONMENT_VARIABLES.md](file://ai_correction/docs/ENVIRONMENT_VARIABLES.md#L1-L100)
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L48-L65)

## Railway部署流程

### 1. 登录Railway

```bash
# 安装Railway CLI（如果尚未安装）
curl -fsSL https://railway.app/install.sh | sh

# 登录账户
railway login
```

### 2. 连接GitHub仓库

```bash
# 创建新项目
railway init

# 连接现有GitHub仓库
railway link

# 选择项目仓库
# 选择您的aiguru项目
```

### 3. 项目结构组织

```mermaid
graph TD
Root[项目根目录] --> Backend[backend/<br/>Streamlit应用]
Root --> Frontend[frontend/<br/>前端应用]
Root --> Config[配置文件]
Backend --> MainPy[main.py<br/>应用入口]
Backend --> ReqTxt[requirements.txt<br/>依赖管理]
Backend --> EnvLocal[.env.local<br/>本地配置]
Frontend --> VercelJson[vercel.json<br/>部署配置]
Frontend --> PackageJson[package.json<br/>前端依赖]
Config --> RailwayToml[railway.toml<br/>服务配置]
Config --> Dockerfile[Dockerfile<br/>容器化]
```

**图表来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L35-L45)
- [vercel.json](file://vercel.json#L1-L1)

**章节来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L15-L35)

## 服务创建与配置

### 后端服务配置

#### 环境变量设置

```bash
# 进入后端目录
cd backend

# 设置环境变量
railway variables set ENVIRONMENT=production
railway variables set PORT=8000
railway variables set DEFAULT_MODE=professional
railway variables set MAX_PARALLEL_WORKERS=8
```

#### 依赖安装配置

Railway会自动检测 `requirements.txt` 文件并安装依赖：

```bash
# requirements.txt内容（自动检测）
streamlit>=1.28.0
langgraph>=0.0.20
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
openai>=1.45.0
```

#### 启动命令配置

```bash
# Railway自动配置的启动命令
streamlit run main.py --server.port=$PORT
```

### 前端服务配置

#### 环境变量设置

```bash
# 进入前端目录
cd ../frontend

# 设置前端环境变量
railway variables set NODE_ENV=production
railway variables set PORT=3000
```

#### 部署配置

```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

**章节来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L48-L87)
- [ai_correction/requirements.txt](file://ai_correction/requirements.txt#L1-L32)

## 数据库服务配置

### PostgreSQL服务创建

```mermaid
sequenceDiagram
participant User as 开发者
participant Railway as Railway平台
participant DB as PostgreSQL服务
User->>Railway : 创建数据库服务
Railway->>DB : 部署PostgreSQL实例
DB-->>Railway : 服务就绪
Railway-->>User : 提供连接信息
User->>Railway : 配置DATABASE_URL
User->>Railway : 执行数据库迁移
Railway->>DB : 执行SQL迁移
DB-->>Railway : 迁移完成
Railway-->>User : 部署成功
```

**图表来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L48-L65)
- [ai_correction/init_database.py](file://ai_correction/init_database.py#L1-L50)

### 数据库连接配置

```bash
# Railway PostgreSQL连接字符串
DATABASE_URL=postgresql://postgres:sfraebGPmjkZtWpAsHqeHrxUrxuDSQFz@postgres.railway.internal:5432/railway

# 本地开发连接字符串
DATABASE_URL=postgresql://user:password@localhost:5432/ai_correction

# SQLite（本地开发）
DATABASE_URL=sqlite:///ai_correction.db
```

### 数据库迁移

```bash
# 进入项目目录
cd ai_correction

# 执行数据库迁移
python functions/database/migration.py upgrade

# 验证迁移状态
python functions/database/migration.py current
```

### 数据库模型定义

系统使用SQLAlchemy ORM定义数据库模型，支持以下核心表：

| 表名 | 用途 | 主要字段 |
|------|------|----------|
| students | 学生信息 | id, student_id, name, class_id |
| grading_tasks | 批改任务 | id, student_id, subject, status |
| grading_results | 批改结果 | id, task_id, question_id, score |
| assignments | 作业管理 | id, assignment_id, class_id, title |
| classes | 班级管理 | id, class_id, class_name, teacher_id |

**章节来源**
- [ai_correction/functions/database/models.py](file://ai_correction/functions/database/models.py#L1-L100)
- [ai_correction/init_database.py](file://ai_correction/init_database.py#L15-L50)

## Redis缓存服务配置

### Redis服务创建

```bash
# 设置Redis连接字符串
REDIS_URL=redis://default:fXZjFSKZfAfkTiqBfomlFHzcddmZZLLv@redis.railway.internal:6379

# 或使用环境变量
railway variables set REDIS_URL=redis://localhost:6379
```

### 缓存配置选项

```bash
# 缓存启用状态
ENABLE_CACHE=true

# 缓存TTL（秒）
CACHE_TTL=3600

# 最大并发连接数
REDIS_MAX_CONNECTIONS=10
```

### 缓存使用场景

1. **会话管理**：用户登录状态缓存
2. **批改结果缓存**：避免重复计算
3. **配置缓存**：系统配置快速访问
4. **临时数据存储**：批改过程中的中间数据

**章节来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L52-L55)
- [ai_correction/config.py](file://ai_correction/config.py#L60-L70)

## 应用部署与启动

### 自动化部署流程

```mermaid
flowchart TD
Start([开始部署]) --> Login[Railway登录检查]
Login --> Link[项目链接验证]
Link --> Build[构建环境准备]
Build --> Install[依赖安装]
Install --> Config[环境变量配置]
Config --> Deploy[应用部署]
Deploy --> Health[健康检查]
Health --> Success{部署成功?}
Success --> |是| End([部署完成])
Success --> |否| Rollback[回滚操作]
Rollback --> Debug[错误诊断]
Debug --> Fix[修复问题]
Fix --> Deploy
```

**图表来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L15-L112)

### 部署命令

```bash
# 后端服务部署
cd backend
railway up --detach

# 前端服务部署  
cd ../frontend
railway up --detach

# 查看部署状态
railway status

# 实时日志监控
railway logs
```

### 启动命令配置

```bash
# Streamlit应用启动命令
streamlit run main.py --server.port=$PORT

# 端口配置
PORT=8000

# 主机绑定
HOST=0.0.0.0
```

### 部署验证

```bash
# 检查服务状态
railway status

# 查看域名配置
railway domain

# 测试应用响应
curl -I https://your-app-name.onrailway.app
```

**章节来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L65-L87)
- [ai_correction/main.py](file://ai_correction/main.py#L1-L50)

## 部署状态验证

### 服务状态检查

```bash
# 查看所有服务状态
railway status

# 查看特定服务详情
railway service

# 查看域名配置
railway domain

# 查看环境变量
railway variables list
```

### 日志监控

```bash
# 实时查看日志
railway logs --follow

# 查看最近错误
railway logs --error

# 查看特定时间段的日志
railway logs --since "1h ago"
```

### 健康检查

```bash
# 检查应用可用性
curl -f https://your-app-name.onrailway.app/health || echo "应用不可用"

# 检查数据库连接
python -c "
from functions.database.models import check_database_connection
print('数据库连接:', check_database_connection())
"

# 检查Redis连接
python -c "
from functions.database.redis_manager import RedisManager
redis = RedisManager()
print('Redis连接:', redis.test_connection())
"
```

### 性能监控

```bash
# 检查资源使用情况
railway resources

# 查看服务指标
railway metrics

# 监控错误率
railway alerts
```

**章节来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L95-L100)
- [ai_correction/local_runner.py](file://ai_correction/local_runner.py#L150-L200)

## 紧急修复流程

### 问题诊断

当部署出现问题时，按照以下流程进行紧急修复：

```mermaid
flowchart TD
Problem[部署失败] --> Check[检查Railway状态]
Check --> Login{是否登录?}
Login --> |否| LoginCmd[railway login]
Login --> |是| Clean[清理失败服务]
LoginCmd --> Clean
Clean --> Relink[重新链接项目]
Relink --> Deploy[重新部署]
Deploy --> Verify[验证部署状态]
Verify --> Success{成功?}
Success --> |是| Complete[修复完成]
Success --> |否| Debug[深入调试]
Debug --> Logs[查看详细日志]
Logs --> Fix[定位具体问题]
Fix --> Deploy
```

**图表来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L15-L112)

### 紧急修复脚本

系统提供了专门的紧急修复脚本：

```python
# 关键修复步骤
def emergency_fix():
    # 1. 检查Railway连接
    run_command("railway whoami")
    
    # 2. 清理失败的服务
    run_command("railway service", check=False)
    
    # 3. 重新链接项目
    run_command("railway unlink", check=False)
    run_command("railway link aiguru2")
    
    # 4. 设置环境变量
    env_vars = [
        "ENVIRONMENT=production",
        "DATABASE_URL=...",
        "REDIS_URL=...",
        "SECRET_KEY=..."
    ]
    
    # 5. 部署应用
    run_command("railway up --detach")
```

### 常见问题及解决方案

| 问题类型 | 症状 | 解决方案 |
|----------|------|----------|
| 数据库连接失败 | SQL错误，无法创建表 | 检查DATABASE_URL，验证连接字符串 |
| 依赖安装失败 | ImportError异常 | 检查requirements.txt，清理缓存 |
| 端口冲突 | 应用无法启动 | 更改PORT环境变量，检查服务占用 |
| API密钥无效 | LLM调用失败 | 验证API密钥，检查环境变量设置 |
| 内存不足 | 应用崩溃 | 增加内存限制，优化批处理大小 |

### 自动化修复流程

```bash
# 1. 检查部署状态
railway status

# 2. 查看错误日志
railway logs --error

# 3. 重新部署
railway up --detach

# 4. 验证修复
curl -f https://your-app.onrailway.app/health
```

**章节来源**
- [urgent_fix_deployment.py](file://urgent_fix_deployment.py#L15-L112)

## 故障排除指南

### 常见部署问题

#### 1. 依赖安装失败

**症状**：构建过程中出现ImportError或PackageNotFoundError

**解决方案**：
```bash
# 检查requirements.txt语法
cat ai_correction/requirements.txt

# 清理pip缓存
pip cache purge

# 重新安装依赖
pip install -r ai_correction/requirements.txt --upgrade
```

#### 2. 数据库连接问题

**症状**：应用启动时报数据库连接错误

**解决方案**：
```bash
# 验证数据库连接字符串
echo $DATABASE_URL

# 测试数据库连接
python -c "
from functions.database.models import check_database_connection
check_database_connection()
"

# 检查数据库服务状态
railway service
```

#### 3. 端口配置问题

**症状**：应用无法访问，端口被占用

**解决方案**：
```bash
# 检查端口占用
netstat -an | grep :8000

# 更改端口配置
railway variables set PORT=8080

# 重新部署
railway up --detach
```

### 性能优化建议

#### 1. 并行处理优化

```bash
# 根据服务器核心数调整
MAX_PARALLEL_WORKERS=4  # 本地开发
MAX_PARALLEL_WORKERS=8  # 生产环境

# 批次大小优化
EFFICIENT_MODE_THRESHOLD=6000
PROFESSIONAL_MODE_THRESHOLD=4000
```

#### 2. 缓存配置优化

```bash
# Redis缓存配置
ENABLE_CACHE=true
CACHE_TTL=3600
REDIS_MAX_CONNECTIONS=10
```

#### 3. 内存管理

```bash
# 监控内存使用
railway resources

# 优化批处理大小
MAX_BATCH_SIZE=10
MEMORY_LIMIT=512MB
```

### 监控和告警

#### 日志配置

```bash
# 日志级别配置
LOG_LEVEL=INFO        # 开发环境
LOG_LEVEL=WARNING     # 生产环境

# 日志文件路径
LOG_FILE=/var/log/ai_correction.log
```

#### 健康检查端点

```python
# 健康检查路由
@app.route('/health')
def health_check():
    return {
        'status': 'healthy',
        'database': check_database_connection(),
        'redis': redis_manager.test_connection(),
        'timestamp': datetime.now().isoformat()
    }
```

**章节来源**
- [ai_correction/docs/DEPLOYMENT_GUIDE.md](file://ai_correction/docs/DEPLOYMENT_GUIDE.md#L250-L310)
- [ai_correction/local_runner.py](file://ai_correction/local_runner.py#L100-L150)

## 最佳实践建议

### 1. 环境管理

- **使用环境变量**：避免硬编码敏感信息
- **版本控制**：只提交`.env.production`模板，不提交实际密钥
- **密钥轮换**：定期更换API密钥和数据库密码
- **环境隔离**：开发、测试、生产环境完全隔离

### 2. 安全配置

```bash
# 安全相关环境变量
SECURE_COOKIES=true
SESSION_TIMEOUT=3600
ENCRYPTION_KEY=${ENCRYPTION_KEY}
```

### 3. 性能优化

```bash
# 性能优化配置
MAX_CONCURRENT_TASKS=10
TASK_TIMEOUT=300
CACHE_ENABLED=true
```

### 4. 监控和维护

```bash
# 监控配置
ENABLE_MONITORING=true
METRICS_ENDPOINT=/metrics
HEALTH_CHECK_INTERVAL=30
```

### 5. 备份策略

```bash
# 数据库备份
BACKUP_SCHEDULE=daily
BACKUP_RETENTION=30
BACKUP_COMPRESSION=gzip
```

### 6. 扩展性考虑

- **水平扩展**：支持多实例部署
- **负载均衡**：使用Railway的自动负载均衡
- **CDN集成**：静态资源使用CDN加速
- **数据库读写分离**：大型应用考虑读写分离

### 7. 开发流程

```bash
# 开发环境配置
ENVIRONMENT=development
DEBUG=true
AUTO_RELOAD=true

# 测试环境配置
ENVIRONMENT=test
TEST_DATABASE_URL=postgresql://test:test@localhost:5432/test_db
```

通过遵循这些最佳实践，您可以确保AI智能批改系统在Railway平台上稳定、安全、高效地运行，为用户提供优质的AI批改服务体验。