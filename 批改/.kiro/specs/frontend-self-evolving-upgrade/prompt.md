# 前端适配自我成长批改系统 - 开发提示词

## 项目背景

AI 批改系统后端已完成"自我成长"架构升级，需要前端进行相应适配。本文档提供前端开发所需的完整提示词和技术规范。

## 新增功能概述

### 1. 流式批改进度 (SSE)
- 通过 Server-Sent Events 实时推送批改进度
- 支持断点续传（基于 sequence_number）
- 事件类型：batch_start, page_complete, batch_complete, student_identified, error, complete

### 2. 学生边界检测
- 自动识别多学生试卷的页面边界
- 低置信度边界需要人工确认
- 按学生分组展示批改结果

### 3. 判例记忆系统
- 教师确认的批改结果可存储为判例
- 支持查看和管理判例库
- 判例用于 few-shot 学习提升批改质量

### 4. 个性化校准配置
- 教师可配置个人评分风格
- 支持容差规则、扣分规则、措辞模板
- 严格程度可调节

### 5. 批改日志与改判
- 完整记录批改过程
- 支持教师改判并记录原因
- 改判数据用于系统自我学习

---

## 开发提示词


### 提示词 1：SSE 流式进度服务

```
请为 AI 批改系统前端实现 SSE (Server-Sent Events) 流式进度服务。

技术要求：
- 使用 TypeScript + React
- 创建 services/sse.ts 服务文件
- 支持自动重连和断点续传

后端 SSE 端点：
- URL: /api/v1/stream/{batch_id}
- 支持 from_sequence 查询参数用于断点续传

事件类型定义：
```typescript
type EventType = 
  | 'batch_start'      // 批次开始
  | 'page_complete'    // 单页完成
  | 'batch_complete'   // 批次完成
  | 'student_identified' // 识别到学生
  | 'error'            // 错误
  | 'complete';        // 全部完成

interface StreamEvent {
  event_type: EventType;
  timestamp: string;
  batch_id: string;
  sequence_number: number;
  data: {
    // batch_start
    total_pages?: number;
    total_batches?: number;
    
    // page_complete
    page_index?: number;
    score?: number;
    confidence?: number;
    
    // student_identified
    student_key?: string;
    start_page?: number;
    end_page?: number;
    needs_confirmation?: boolean;
    
    // error
    error_message?: string;
    retry_suggestion?: string;
  };
}
```

功能要求：
1. 创建 SSEClient 类，支持连接、断开、重连
2. 实现 useSSE hook，返回连接状态和事件数据
3. 支持断点续传：断开后从 last_sequence_number + 1 继续
4. 最大重连次数 5 次，指数退避策略
5. 提供 TypeScript 类型定义
```


### 提示词 2：实时批改进度组件

```
请为 AI 批改系统前端实现实时批改进度展示组件。

技术要求：
- 使用 React + TypeScript + Tailwind CSS
- 集成 SSE 服务获取实时进度
- 响应式设计，支持移动端

组件结构：
1. BatchProgressView - 主容器组件
2. ProgressTimeline - 时间线展示批次进度
3. PageProgressGrid - 网格展示各页面状态
4. StudentBoundaryAlert - 学生边界确认提示

UI 要求：
1. 顶部显示总体进度条和预计剩余时间
2. 中间区域显示批次时间线：
   - 每个批次显示为一个节点
   - 节点状态：pending(灰色), processing(蓝色动画), completed(绿色), error(红色)
3. 下方显示页面网格：
   - 每页显示为一个小卡片
   - 显示页码、得分、置信度
   - 低置信度(<0.75)用橙色边框标记
4. 当检测到学生边界时，弹出确认对话框：
   - 显示检测到的学生信息
   - 如果 needs_confirmation=true，要求用户确认或调整

状态管理：
- 使用 Zustand 存储进度状态
- 支持页面刷新后恢复进度（从 localStorage 读取 last_sequence）

示例数据结构：
```typescript
interface BatchProgress {
  batchId: string;
  totalPages: number;
  totalBatches: number;
  currentBatch: number;
  completedPages: number;
  pageResults: PageResult[];
  students: StudentBoundary[];
  status: 'connecting' | 'processing' | 'completed' | 'error';
  lastSequence: number;
}
```
```


### 提示词 3：学生分组结果展示

```
请为 AI 批改系统前端实现按学生分组的批改结果展示页面。

技术要求：
- 使用 React + TypeScript + Tailwind CSS
- 支持折叠/展开学生详情
- 图片查看器支持缩放和标注

后端 API：
- GET /api/v1/batch/{batch_id}/results - 获取批改结果
- GET /api/v1/batch/{batch_id}/students - 获取学生分组

数据结构：
```typescript
interface StudentBoundary {
  student_key: string;      // 学生标识（姓名/学号）
  start_page: number;
  end_page: number;
  confidence: float;
  needs_confirmation: boolean;
  total_score?: number;
  max_score?: number;
}

interface StudentGradingResult {
  student: StudentBoundary;
  pages: PageResult[];
  questions: QuestionResult[];
}
```

页面布局：
1. 左侧学生列表（可折叠侧边栏）：
   - 显示学生姓名/学号
   - 显示总分和页面范围
   - 需确认的学生用警告图标标记
   
2. 右侧详情区域：
   - 顶部显示学生信息卡片
   - 中间显示试卷图片（支持翻页）
   - 底部显示各题目得分详情

3. 学生边界调整功能：
   - 当 needs_confirmation=true 时显示调整按钮
   - 点击后弹出对话框，允许拖拽调整页面范围
   - 调用 PUT /api/v1/batch/{batch_id}/students/{student_key}/boundary 保存

交互要求：
1. 点击学生切换详情
2. 支持键盘快捷键：↑↓切换学生，←→翻页
3. 图片支持双击放大、滚轮缩放
4. 标注区域悬停显示评分详情
```


### 提示词 4：判例管理界面

```
请为 AI 批改系统前端实现判例（Exemplar）管理界面。

功能说明：
判例是教师确认过的正确批改示例，系统会用这些判例进行 few-shot 学习，提升批改质量。

后端 API：
- POST /api/v1/exemplars - 创建判例（从批改结果确认）
- GET /api/v1/exemplars - 获取判例列表（支持分页和筛选）
- GET /api/v1/exemplars/{id} - 获取判例详情
- DELETE /api/v1/exemplars/{id} - 删除判例

数据结构：
```typescript
interface Exemplar {
  exemplar_id: string;
  question_type: 'objective' | 'stepwise' | 'essay' | 'lab_design';
  question_image_hash: string;
  student_answer_text: string;
  score: number;
  max_score: number;
  teacher_feedback: string;
  teacher_id: string;
  confirmed_at: string;
  usage_count: number;  // 被检索使用的次数
}

interface ExemplarCreateRequest {
  grading_log_id: string;  // 从批改日志创建
  teacher_feedback: string;
}
```

页面布局：
1. 判例列表页：
   - 顶部筛选栏：题型、时间范围、使用次数
   - 表格展示：题型、答案预览、得分、确认时间、使用次数
   - 支持批量删除
   
2. 判例详情弹窗：
   - 左侧显示题目图片
   - 右侧显示：学生答案、得分、教师评语
   - 底部显示使用统计

3. 从批改结果创建判例：
   - 在批改结果页面添加"确认为判例"按钮
   - 点击后弹出对话框，填写教师评语
   - 提交后显示成功提示

交互要求：
1. 列表支持无限滚动加载
2. 删除前二次确认
3. 创建成功后显示 Toast 提示
```


### 提示词 5：教师校准配置界面

```
请为 AI 批改系统前端实现教师个性化校准配置界面。

功能说明：
教师可以配置个人的评分风格，系统会根据配置调整批改行为。

后端 API：
- GET /api/v1/calibration/profile - 获取当前教师的校准配置
- PUT /api/v1/calibration/profile - 更新校准配置
- POST /api/v1/calibration/profile/reset - 重置为默认配置

数据结构：
```typescript
interface CalibrationProfile {
  profile_id: string;
  teacher_id: string;
  school_id?: string;
  
  // 扣分规则
  deduction_rules: {
    [error_type: string]: number;  // 错误类型 -> 扣分值
  };
  
  // 容差规则
  tolerance_rules: ToleranceRule[];
  
  // 措辞模板
  feedback_templates: {
    [scenario: string]: string;  // 场景 -> 模板
  };
  
  // 严格程度 0.0-1.0
  strictness_level: number;
}

interface ToleranceRule {
  rule_type: 'numeric' | 'unit' | 'synonym';
  tolerance_value: number;
  description: string;
}
```

页面布局：
1. 严格程度滑块：
   - 0.0 = 宽松，1.0 = 严格
   - 显示当前值和说明文字
   - 实时预览效果

2. 扣分规则配置：
   - 表格形式展示错误类型和扣分值
   - 支持添加、编辑、删除规则
   - 常见错误类型：计算错误、单位错误、步骤缺失、表述不清

3. 容差规则配置：
   - 数值容差：允许的误差范围（如 ±0.01）
   - 单位容差：允许的单位换算（如 m/cm）
   - 同义词容差：允许的同义表达

4. 措辞模板配置：
   - 场景列表：满分、部分得分、零分、鼓励
   - 每个场景可配置模板文本
   - 支持变量插入：{score}, {max_score}, {feedback}

交互要求：
1. 修改后自动保存（防抖 500ms）
2. 显示保存状态指示器
3. 重置前二次确认
4. 提供预览功能，展示配置效果
```


### 提示词 6：批改日志与改判界面

```
请为 AI 批改系统前端实现批改日志查看和改判功能界面。

功能说明：
教师可以查看完整的批改日志，对不满意的结果进行改判。改判数据会被系统学习，用于提升批改质量。

后端 API：
- GET /api/v1/grading-logs?submission_id={id} - 获取批改日志列表
- GET /api/v1/grading-logs/{log_id} - 获取日志详情
- POST /api/v1/grading-logs/{log_id}/override - 提交改判

数据结构：
```typescript
interface GradingLog {
  log_id: string;
  submission_id: string;
  question_id: string;
  timestamp: string;
  
  // 提取阶段
  extracted_answer: string;
  extraction_confidence: number;
  evidence_snippets: string[];
  
  // 规范化阶段
  normalized_answer?: string;
  normalization_rules_applied: string[];
  
  // 匹配阶段
  match_result: boolean;
  match_failure_reason?: string;
  
  // 评分阶段
  score: number;
  max_score: number;
  confidence: number;
  reasoning_trace: string[];
  
  // 改判信息
  was_overridden: boolean;
  override_score?: number;
  override_reason?: string;
  override_teacher_id?: string;
}

interface OverrideRequest {
  override_score: number;
  override_reason: string;
}
```

页面布局：
1. 日志列表视图：
   - 按题目分组显示
   - 显示：题号、AI得分、置信度、是否已改判
   - 已改判的显示改判后分数
   - 低置信度用橙色标记

2. 日志详情面板（点击展开）：
   - 推理过程时间线：
     - 提取阶段：显示识别的答案和证据
     - 规范化阶段：显示应用的规则
     - 匹配阶段：显示匹配结果
     - 评分阶段：显示推理步骤
   - 每个阶段显示置信度

3. 改判对话框：
   - 显示原始得分和 AI 推理
   - 输入新分数（数字输入框，范围验证）
   - 输入改判原因（必填，最少 10 字）
   - 提交按钮

交互要求：
1. 列表支持按置信度、是否改判筛选
2. 改判后实时更新列表
3. 显示改判统计：总改判数、改判率
4. 支持批量查看低置信度题目
```


### 提示词 7：规则升级监控仪表盘

```
请为 AI 批改系统前端实现规则升级监控仪表盘（管理员功能）。

功能说明：
系统会自动从教师改判中学习，生成规则补丁。管理员可以监控规则升级的状态和效果。

后端 API：
- GET /api/v1/admin/rule-patches - 获取补丁列表
- GET /api/v1/admin/rule-patches/{id} - 获取补丁详情
- POST /api/v1/admin/rule-patches/{id}/deploy - 部署补丁
- POST /api/v1/admin/rule-patches/{id}/rollback - 回滚补丁
- GET /api/v1/admin/rule-patches/stats - 获取统计数据

数据结构：
```typescript
interface RulePatch {
  patch_id: string;
  patch_type: 'rule' | 'prompt' | 'exemplar';
  version: string;
  description: string;
  content: object;
  source_pattern_id: string;
  status: 'candidate' | 'testing' | 'canary' | 'deployed' | 'rolled_back';
  created_at: string;
  deployed_at?: string;
  
  // 回归测试结果
  regression_result?: {
    passed: boolean;
    old_error_rate: number;
    new_error_rate: number;
    improved_samples: number;
    degraded_samples: number;
  };
}

interface PatchStats {
  total_patches: number;
  deployed_patches: number;
  pending_patches: number;
  average_improvement: number;  // 平均误判率下降
  last_deployment: string;
}
```

页面布局：
1. 统计卡片区：
   - 总补丁数、已部署数、待处理数
   - 平均改进率
   - 最近部署时间

2. 补丁列表：
   - 表格：版本、类型、状态、创建时间、操作
   - 状态徽章：不同颜色区分状态
   - 操作按钮：查看详情、部署、回滚

3. 补丁详情弹窗：
   - 基本信息：版本、类型、描述
   - 来源模式：显示触发补丁生成的失败模式
   - 回归测试结果：
     - 误判率对比图表
     - 改进/退化样本数
   - 部署历史时间线

4. 部署确认对话框：
   - 显示回归测试结果
   - 选择部署范围：灰度(10%) / 全量
   - 确认按钮

交互要求：
1. 实时刷新补丁状态（轮询 30s）
2. 部署/回滚操作需要二次确认
3. 显示操作进度和结果
4. 支持按状态、类型筛选
```


### 提示词 8：API 服务层扩展

```
请扩展 AI 批改系统前端的 API 服务层，添加自我成长功能相关的 API 调用。

技术要求：
- 使用 TypeScript
- 基于现有的 services/api.ts 扩展
- 添加完整的类型定义
- 统一错误处理

新增 API 模块：

```typescript
// services/api.ts 扩展

// ============ 流式服务 ============
export const streamApi = {
  // 获取 SSE 连接 URL
  getStreamUrl: (batchId: string, fromSequence?: number): string => {
    const base = `${API_BASE_URL}/api/v1/stream/${batchId}`;
    return fromSequence ? `${base}?from_sequence=${fromSequence}` : base;
  },
};

// ============ 学生边界 ============
export const studentApi = {
  // 获取学生分组
  getStudents: async (batchId: string): Promise<StudentBoundary[]> => {},
  
  // 更新学生边界
  updateBoundary: async (
    batchId: string, 
    studentKey: string, 
    boundary: { start_page: number; end_page: number }
  ): Promise<void> => {},
  
  // 确认学生边界
  confirmBoundary: async (batchId: string, studentKey: string): Promise<void> => {},
};

// ============ 判例管理 ============
export const exemplarApi = {
  // 创建判例
  create: async (data: ExemplarCreateRequest): Promise<Exemplar> => {},
  
  // 获取判例列表
  list: async (params: {
    question_type?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Exemplar>> => {},
  
  // 获取判例详情
  get: async (id: string): Promise<Exemplar> => {},
  
  // 删除判例
  delete: async (id: string): Promise<void> => {},
};

// ============ 校准配置 ============
export const calibrationApi = {
  // 获取配置
  getProfile: async (): Promise<CalibrationProfile> => {},
  
  // 更新配置
  updateProfile: async (data: Partial<CalibrationProfile>): Promise<CalibrationProfile> => {},
  
  // 重置配置
  resetProfile: async (): Promise<CalibrationProfile> => {},
};

// ============ 批改日志 ============
export const gradingLogApi = {
  // 获取日志列表
  list: async (submissionId: string): Promise<GradingLog[]> => {},
  
  // 获取日志详情
  get: async (logId: string): Promise<GradingLog> => {},
  
  // 提交改判
  override: async (logId: string, data: OverrideRequest): Promise<void> => {},
  
  // 获取改判统计
  getOverrideStats: async (params: {
    days?: number;
  }): Promise<{ total: number; rate: number }> => {},
};

// ============ 规则补丁（管理员）============
export const rulePatchApi = {
  // 获取补丁列表
  list: async (params?: {
    status?: string;
    type?: string;
  }): Promise<RulePatch[]> => {},
  
  // 获取补丁详情
  get: async (id: string): Promise<RulePatch> => {},
  
  // 部署补丁
  deploy: async (id: string, scope: 'canary' | 'full'): Promise<void> => {},
  
  // 回滚补丁
  rollback: async (id: string): Promise<void> => {},
  
  // 获取统计
  getStats: async (): Promise<PatchStats> => {},
};
```

错误处理：
- 429 错误：解析 Retry-After，自动重试
- 401 错误：跳转登录页
- 500 错误：显示友好错误信息
```


### 提示词 9：状态管理扩展

```
请扩展 AI 批改系统前端的 Zustand 状态管理，添加自我成长功能相关的状态。

技术要求：
- 使用 Zustand
- 支持持久化（localStorage）
- 类型安全

新增状态模块：

```typescript
// store/batchProgressStore.ts
interface BatchProgressState {
  // 当前批次进度
  currentBatch: BatchProgress | null;
  
  // 历史进度（用于断点续传）
  progressHistory: Map<string, BatchProgress>;
  
  // 操作
  setProgress: (progress: BatchProgress) => void;
  updatePageResult: (pageIndex: number, result: PageResult) => void;
  addStudent: (student: StudentBoundary) => void;
  setStatus: (status: BatchProgress['status']) => void;
  clearProgress: (batchId: string) => void;
  
  // 持久化
  saveToStorage: () => void;
  loadFromStorage: (batchId: string) => BatchProgress | null;
}

// store/exemplarStore.ts
interface ExemplarState {
  exemplars: Exemplar[];
  selectedExemplar: Exemplar | null;
  filters: {
    questionType: string | null;
    dateRange: [Date, Date] | null;
  };
  
  setExemplars: (exemplars: Exemplar[]) => void;
  addExemplar: (exemplar: Exemplar) => void;
  removeExemplar: (id: string) => void;
  selectExemplar: (exemplar: Exemplar | null) => void;
  setFilters: (filters: Partial<ExemplarState['filters']>) => void;
}

// store/calibrationStore.ts
interface CalibrationState {
  profile: CalibrationProfile | null;
  isDirty: boolean;
  isSaving: boolean;
  
  setProfile: (profile: CalibrationProfile) => void;
  updateProfile: (updates: Partial<CalibrationProfile>) => void;
  setSaving: (saving: boolean) => void;
  resetDirty: () => void;
}

// store/gradingLogStore.ts
interface GradingLogState {
  logs: GradingLog[];
  selectedLog: GradingLog | null;
  overrideStats: { total: number; rate: number } | null;
  
  setLogs: (logs: GradingLog[]) => void;
  updateLog: (logId: string, updates: Partial<GradingLog>) => void;
  selectLog: (log: GradingLog | null) => void;
  setOverrideStats: (stats: { total: number; rate: number }) => void;
}
```

持久化配置：
```typescript
import { persist } from 'zustand/middleware';

export const useBatchProgressStore = create<BatchProgressState>()(
  persist(
    (set, get) => ({
      // ... 实现
    }),
    {
      name: 'batch-progress-storage',
      partialize: (state) => ({
        progressHistory: state.progressHistory,
      }),
    }
  )
);
```
```


### 提示词 10：路由和导航更新

```
请更新 AI 批改系统前端的路由配置，添加自我成长功能相关的页面路由。

技术要求：
- 使用 Next.js App Router
- 支持动态路由
- 添加权限控制

新增路由：

```
/console
├── /batch
│   ├── /[batchId]              # 批次详情（含实时进度）
│   │   ├── /progress           # 进度监控
│   │   ├── /results            # 结果展示（按学生分组）
│   │   └── /logs               # 批改日志
│   └── /history                # 批次历史
├── /exemplars                  # 判例管理
│   ├── /                       # 判例列表
│   └── /[exemplarId]           # 判例详情
├── /calibration                # 校准配置
│   └── /                       # 配置页面
├── /admin                      # 管理员功能
│   ├── /rule-patches           # 规则补丁管理
│   │   ├── /                   # 补丁列表
│   │   └── /[patchId]          # 补丁详情
│   └── /stats                  # 系统统计
└── /settings                   # 设置
    └── /profile                # 个人设置
```

导航菜单更新：
```typescript
const navigationItems = [
  {
    title: '批改管理',
    icon: FileTextIcon,
    items: [
      { title: '新建批改', href: '/console/batch/new' },
      { title: '批改历史', href: '/console/batch/history' },
    ],
  },
  {
    title: '自我成长',
    icon: BrainIcon,
    items: [
      { title: '判例库', href: '/console/exemplars' },
      { title: '校准配置', href: '/console/calibration' },
    ],
  },
  {
    title: '管理员',
    icon: SettingsIcon,
    requireAdmin: true,
    items: [
      { title: '规则补丁', href: '/console/admin/rule-patches' },
      { title: '系统统计', href: '/console/admin/stats' },
    ],
  },
];
```

权限控制：
- /admin/* 路由需要管理员权限
- 使用中间件检查权限
- 无权限时重定向到首页
```

---

## 开发优先级建议

1. **P0 - 核心功能**
   - SSE 流式进度服务
   - 实时批改进度组件
   - 学生分组结果展示

2. **P1 - 重要功能**
   - 批改日志与改判界面
   - 判例管理界面

3. **P2 - 增强功能**
   - 教师校准配置界面
   - 规则升级监控仪表盘

---

## 技术注意事项

1. **SSE 连接管理**
   - 页面切换时正确关闭连接
   - 支持断点续传避免数据丢失
   - 处理网络不稳定情况

2. **状态同步**
   - SSE 事件与本地状态保持一致
   - 使用乐观更新提升体验
   - 冲突时以服务端为准

3. **性能优化**
   - 大量页面结果使用虚拟列表
   - 图片懒加载
   - 防抖处理频繁更新

4. **错误处理**
   - 网络错误友好提示
   - 操作失败可重试
   - 保留用户输入数据
```

