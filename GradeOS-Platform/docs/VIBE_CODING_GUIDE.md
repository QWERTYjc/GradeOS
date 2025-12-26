# GradeOS 多人 Vibe Coding 协作指南

> 面向 AI 辅助开发的团队协作范式与架构优化建议

## 📋 目录

- [Vibe Coding 概述](#vibe-coding-概述)
- [项目模块划分](#项目模块划分)
- [协作工作流](#协作工作流)
- [架构优化建议](#架构优化建议)
- [AI 辅助开发最佳实践](#ai-辅助开发最佳实践)
- [代码质量保障](#代码质量保障)

---

## Vibe Coding 概述

### 什么是 Vibe Coding？

Vibe Coding 是一种以 AI 为核心辅助工具的协作开发范式，强调：

1. **意图驱动** - 用自然语言描述需求，AI 生成代码
2. **快速迭代** - 通过对话式交互快速原型和修改
3. **并行开发** - 多人同时在不同模块工作，AI 协调整合
4. **知识共享** - AI 作为团队知识库，保持上下文一致性

### 为什么适合 GradeOS？

GradeOS 整合了四个独立项目，天然具有模块化特性：

```
┌─────────────────────────────────────────────────────────────┐
│                    GradeOS Platform                          │
├─────────────┬─────────────┬─────────────┬─────────────────────┤
│  AI 批改    │  教师管理   │  学生助手   │  错题分析           │
│  (批改/)    │  (GradeOS-  │  (student-  │  (intellilearn/)    │
│             │  frontend/) │  assisant/) │                     │
├─────────────┴─────────────┴─────────────┴─────────────────────┤
│                    统一 API 层 + 共享组件                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 项目模块划分

### 推荐的团队分工

| 角色 | 负责模块 | 主要文件 | 技能要求 |
|------|----------|----------|----------|
| **后端开发 A** | 统一 API + 数据库 | `backend/src/api/routes/unified_api.py`<br>`backend/src/models/unified_models.py` | Python, FastAPI, PostgreSQL |
| **后端开发 B** | AI 批改引擎 | `backend/src/agents/`<br>`backend/src/graphs/`<br>`backend/src/services/` | Python, LangGraph, Gemini API |
| **前端开发 A** | 教师模块 | `frontend/src/app/teacher/`<br>`frontend/src/components/` | React, Next.js, TypeScript |
| **前端开发 B** | 学生模块 | `frontend/src/app/student/`<br>`frontend/src/services/api.ts` | React, Next.js, Recharts |
| **前端开发 C** | 批改控制台 | `frontend/src/app/console/`<br>`frontend/src/store/consoleStore.ts` | React, WebSocket, 动画 |
| **全栈/架构** | 集成 + DevOps | `docker-compose.yml`<br>CI/CD 配置 | Docker, K8s, 系统设计 |

### 模块边界定义

```yaml
# 模块依赖关系
modules:
  unified_api:
    owner: backend-a
    dependencies: []
    exports:
      - /api/auth/*
      - /api/class/*
      - /api/homework/*
      - /api/v1/analysis/*
      - /api/teacher/statistics/*

  grading_engine:
    owner: backend-b
    dependencies: [unified_api]
    exports:
      - /submissions/*
      - /batch/*
      - /rubrics/*

  teacher_frontend:
    owner: frontend-a
    dependencies: [unified_api]
    pages:
      - /teacher/dashboard
      - /teacher/homework
      - /teacher/statistics
      - /teacher/class/[id]

  student_frontend:
    owner: frontend-b
    dependencies: [unified_api]
    pages:
      - /student/dashboard
      - /student/assistant
      - /student/analysis
      - /student/report

  console_frontend:
    owner: frontend-c
    dependencies: [grading_engine]
    pages:
      - /console
```

---

## 协作工作流

### 1. 任务分配流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  需求文档   │────▶│  AI 分解    │────▶│  任务分配   │
│  (PRD)      │     │  任务       │     │  (Jira/     │
│             │     │             │     │  Linear)    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
       ┌───────────────────────────────────────┼───────────────────────────────────────┐
       │                                       │                                       │
       ▼                                       ▼                                       ▼
┌─────────────┐                         ┌─────────────┐                         ┌─────────────┐
│  开发者 A   │                         │  开发者 B   │                         │  开发者 C   │
│  + AI 助手  │                         │  + AI 助手  │                         │  + AI 助手  │
└──────┬──────┘                         └──────┬──────┘                         └──────┬──────┘
       │                                       │                                       │
       ▼                                       ▼                                       ▼
┌─────────────┐                         ┌─────────────┐                         ┌─────────────┐
│  Feature    │                         │  Feature    │                         │  Feature    │
│  Branch A   │                         │  Branch B   │                         │  Branch C   │
└──────┬──────┘                         └──────┬──────┘                         └──────┬──────┘
       │                                       │                                       │
       └───────────────────────────────────────┼───────────────────────────────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  PR Review  │
                                        │  + AI 检查  │
                                        └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   Merge     │
                                        │   develop   │
                                        └─────────────┘
```

### 2. AI 辅助开发会话模板

每个开发者在开始工作时，应向 AI 提供上下文：

```markdown
## 会话上下文

**项目**: GradeOS Platform
**模块**: [你负责的模块]
**当前任务**: [任务描述]

**相关文件**:
- `path/to/file1.ts`
- `path/to/file2.py`

**接口约定**:
- API 基础路径: `/api`
- 认证方式: JWT Token
- 响应格式: `{ data, error, message }`

**注意事项**:
- 遵循现有代码风格
- 使用 TypeScript 严格模式
- 添加中文注释
```

### 3. 接口协商流程

当模块间需要新接口时：

```
1. 需求方在 `docs/api-proposals/` 创建提案
2. AI 辅助生成接口定义 (OpenAPI/TypeScript)
3. 相关开发者 Review
4. 合并到 `docs/api-contracts/`
5. 各方按契约实现
```

**接口提案模板** (`docs/api-proposals/xxx.md`):

```markdown
# 接口提案: [功能名称]

## 背景
[为什么需要这个接口]

## 接口定义

### Request
```typescript
POST /api/xxx
Content-Type: application/json

{
  "field1": string,
  "field2": number
}
```

### Response
```typescript
{
  "data": {
    "id": string,
    "result": object
  },
  "error": null
}
```

## 影响范围
- 前端: `frontend/src/services/api.ts`
- 后端: `backend/src/api/routes/xxx.py`

## 时间线
- 提案: 2024-12-25
- 评审: 2024-12-26
- 实现: 2024-12-27
```


---

## 架构优化建议

### 1. 后端架构优化

#### 1.1 API 层优化

**当前状态**: 单一 `unified_api.py` 文件包含所有路由

**优化方案**: 按领域拆分

```
backend/src/api/routes/
├── __init__.py
├── auth.py           # 认证相关
├── classes.py        # 班级管理
├── homework.py       # 作业管理
├── analysis.py       # 错题分析
├── statistics.py     # 统计分析
└── grading.py        # AI 批改 (已有)
```

**实施步骤**:

```python
# backend/src/api/routes/__init__.py
from .auth import router as auth_router
from .classes import router as classes_router
from .homework import router as homework_router
from .analysis import router as analysis_router
from .statistics import router as statistics_router

__all__ = [
    "auth_router",
    "classes_router", 
    "homework_router",
    "analysis_router",
    "statistics_router",
]
```

#### 1.2 服务层优化

**引入 Repository 模式**:

```python
# backend/src/repositories/class_repository.py
class ClassRepository:
    def __init__(self, db: Database):
        self.db = db
    
    async def get_by_id(self, class_id: str) -> Optional[Class]:
        async with self.db.connection() as conn:
            result = await conn.execute(
                "SELECT * FROM classes WHERE class_id = %s",
                (class_id,)
            )
            return Class(**result) if result else None
    
    async def get_by_teacher(self, teacher_id: str) -> List[Class]:
        ...

# backend/src/services/class_service.py
class ClassService:
    def __init__(self, repo: ClassRepository, cache: CacheService):
        self.repo = repo
        self.cache = cache
    
    async def get_teacher_classes(self, teacher_id: str) -> List[Class]:
        # 先查缓存
        cached = await self.cache.get(f"teacher:{teacher_id}:classes")
        if cached:
            return cached
        
        # 查数据库
        classes = await self.repo.get_by_teacher(teacher_id)
        
        # 写缓存
        await self.cache.set(f"teacher:{teacher_id}:classes", classes, ttl=300)
        
        return classes
```

#### 1.3 依赖注入优化

```python
# backend/src/api/dependencies.py
from functools import lru_cache

@lru_cache()
def get_class_repository() -> ClassRepository:
    return ClassRepository(db)

@lru_cache()
def get_class_service() -> ClassService:
    return ClassService(
        repo=get_class_repository(),
        cache=get_cache_service()
    )

# 在路由中使用
@router.get("/teacher/classes")
async def get_teacher_classes(
    teacher_id: str,
    service: ClassService = Depends(get_class_service)
):
    return await service.get_teacher_classes(teacher_id)
```

### 2. 前端架构优化

#### 2.1 API 层优化

**当前状态**: 单一 `api.ts` 文件

**优化方案**: 按领域拆分 + React Query

```
frontend/src/services/
├── api/
│   ├── client.ts         # 基础请求客户端
│   ├── auth.ts           # 认证 API
│   ├── classes.ts        # 班级 API
│   ├── homework.ts       # 作业 API
│   ├── analysis.ts       # 错题分析 API
│   └── index.ts          # 统一导出
├── hooks/
│   ├── useAuth.ts        # 认证 hooks
│   ├── useClasses.ts     # 班级 hooks
│   ├── useHomework.ts    # 作业 hooks
│   └── useAnalysis.ts    # 分析 hooks
└── index.ts
```

**示例实现**:

```typescript
// frontend/src/services/api/client.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5分钟
      retry: 1,
    },
  },
});

export async function apiClient<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
      ...options?.headers,
    },
    ...options,
  });
  
  if (!response.ok) {
    throw new ApiError(response.status, await response.json());
  }
  
  return response.json();
}

// frontend/src/services/hooks/useClasses.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export function useTeacherClasses(teacherId: string) {
  return useQuery({
    queryKey: ['classes', 'teacher', teacherId],
    queryFn: () => classApi.getTeacherClasses(teacherId),
    enabled: !!teacherId,
  });
}

export function useCreateClass() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: classApi.createClass,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['classes'] });
    },
  });
}
```

#### 2.2 状态管理优化

**当前状态**: Zustand 单一 store

**优化方案**: 按领域拆分 + 持久化

```typescript
// frontend/src/store/index.ts
import { create } from 'zustand';
import { persist, devtools } from 'zustand/middleware';

// 认证 Store
export const useAuthStore = create<AuthState>()(
  devtools(
    persist(
      (set) => ({
        user: null,
        token: null,
        login: async (credentials) => { ... },
        logout: () => set({ user: null, token: null }),
      }),
      { name: 'auth-storage' }
    )
  )
);

// UI Store (不持久化)
export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  theme: 'light',
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
```

#### 2.3 组件架构优化

**引入 Feature-Sliced Design**:

```
frontend/src/
├── app/                    # Next.js App Router
├── features/               # 功能模块
│   ├── auth/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── api/
│   │   └── index.ts
│   ├── classes/
│   ├── homework/
│   └── analysis/
├── shared/                 # 共享资源
│   ├── ui/                 # 基础 UI 组件
│   ├── lib/                # 工具函数
│   └── config/             # 配置
└── widgets/                # 组合组件
    ├── DashboardLayout/
    └── DataTable/
```

### 3. 数据库优化

#### 3.1 读写分离

```yaml
# docker-compose.prod.yml
services:
  postgres-primary:
    image: postgres:15
    environment:
      POSTGRES_REPLICATION_MODE: master
    
  postgres-replica:
    image: postgres:15
    environment:
      POSTGRES_REPLICATION_MODE: slave
      POSTGRES_MASTER_HOST: postgres-primary
```

```python
# backend/src/utils/database.py
class Database:
    def __init__(self):
        self.write_pool = AsyncConnectionPool(WRITE_DB_URL)
        self.read_pool = AsyncConnectionPool(READ_DB_URL)
    
    @asynccontextmanager
    async def read_connection(self):
        async with self.read_pool.connection() as conn:
            yield conn
    
    @asynccontextmanager
    async def write_connection(self):
        async with self.write_pool.connection() as conn:
            yield conn
```

#### 3.2 缓存策略优化

```python
# backend/src/services/cache.py
class CacheService:
    """多级缓存服务"""
    
    def __init__(self, redis: Redis):
        self.redis = redis
        self.local_cache = TTLCache(maxsize=1000, ttl=60)
    
    async def get(self, key: str) -> Optional[Any]:
        # L1: 本地缓存
        if key in self.local_cache:
            return self.local_cache[key]
        
        # L2: Redis
        value = await self.redis.get(key)
        if value:
            self.local_cache[key] = value
            return value
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        self.local_cache[key] = value
        await self.redis.setex(key, ttl, value)
```

---

## AI 辅助开发最佳实践

### 1. Prompt 工程

#### 代码生成 Prompt 模板

```markdown
## 任务
[具体任务描述]

## 上下文
- 项目: GradeOS Platform
- 语言: [Python/TypeScript]
- 框架: [FastAPI/Next.js]

## 相关代码
```[language]
[现有相关代码]
```

## 要求
1. 遵循现有代码风格
2. 添加类型注解
3. 包含错误处理
4. 添加中文注释

## 输出格式
只输出代码，不需要解释
```

#### Code Review Prompt 模板

```markdown
## 请审查以下代码

```[language]
[待审查代码]
```

## 审查要点
1. 代码质量和可读性
2. 潜在的 bug 或边界情况
3. 性能问题
4. 安全漏洞
5. 是否符合项目规范

## 输出格式
- 问题列表 (按严重程度排序)
- 改进建议
- 优化后的代码 (如需要)
```

### 2. 上下文管理

#### 项目级 Steering 文件

创建 `.kiro/steering/project-context.md`:

```markdown
---
inclusion: always
---

# GradeOS 项目上下文

## 技术栈
- 后端: Python 3.11+, FastAPI, LangGraph, PostgreSQL, Redis
- 前端: Next.js 15, React 19, TypeScript, Tailwind CSS, Zustand

## 代码规范
- Python: Black 格式化, 类型注解必须
- TypeScript: 严格模式, ESLint + Prettier
- 提交信息: Conventional Commits

## API 约定
- 基础路径: `/api`
- 认证: JWT Bearer Token
- 响应格式: `{ data, error, message }`

## 数据库
- 19 张核心表，详见 `后端数据库需求文档_基于API整合.md`
- 使用 PostgreSQL JSONB 存储灵活数据
```

### 3. 协作 AI 会话

#### 跨模块协作示例

**场景**: 前端需要新的 API 接口

```markdown
## 会话 1 (前端开发者)

我需要一个获取学生错题统计的接口，用于学情报告页面。

需要的数据:
- 各科目错题数量
- 错误类型分布
- 近30天趋势

请帮我:
1. 设计接口请求/响应格式
2. 生成 TypeScript 类型定义
3. 生成 API 调用函数
```

```markdown
## 会话 2 (后端开发者)

前端需要以下接口，请帮我实现:

接口: GET /api/v1/student/{student_id}/error-statistics
响应:
```typescript
{
  by_subject: { [subject: string]: number },
  by_error_type: { [type: string]: number },
  trend_30d: { date: string, count: number }[]
}
```

要求:
1. 使用现有的 error_records 表
2. 添加 Redis 缓存 (TTL 10分钟)
3. 遵循现有代码风格
```

---

## 代码质量保障

### 1. 自动化检查

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install black isort flake8 pytest
      
      - name: Lint
        run: |
          cd backend
          black --check src/
          isort --check src/
          flake8 src/
      
      - name: Test
        run: |
          cd backend
          pytest tests/ -v

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Lint
        run: |
          cd frontend
          npm run lint
      
      - name: Type check
        run: |
          cd frontend
          npm run type-check
      
      - name: Test
        run: |
          cd frontend
          npm test
```

### 2. Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        files: ^backend/

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        files: ^backend/

  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.56.0
    hooks:
      - id: eslint
        files: ^frontend/.*\.[jt]sx?$
        additional_dependencies:
          - eslint@8.56.0
          - typescript
```

### 3. AI 辅助 Code Review

在 PR 描述中添加:

```markdown
## AI Review Checklist

- [ ] 代码符合项目规范
- [ ] 添加了必要的类型注解
- [ ] 包含错误处理
- [ ] 有适当的测试覆盖
- [ ] 更新了相关文档

## AI 审查结果

[粘贴 AI 审查输出]
```

---

## 总结

### Vibe Coding 成功要素

1. **清晰的模块边界** - 减少冲突，提高并行度
2. **统一的接口契约** - API 先行，前后端解耦
3. **一致的上下文** - Steering 文件 + 项目文档
4. **自动化质量保障** - CI/CD + Pre-commit
5. **有效的 AI 协作** - 结构化 Prompt + 上下文管理

### 推荐工具链

| 用途 | 工具 |
|------|------|
| AI 辅助开发 | Kiro, Cursor, GitHub Copilot |
| 任务管理 | Linear, Jira |
| 文档协作 | Notion, Confluence |
| API 设计 | Swagger, Postman |
| 代码审查 | GitHub PR, GitLab MR |
| 监控告警 | Sentry, Datadog |

---

*文档版本: v1.0*  
*最后更新: 2024-12-25*
