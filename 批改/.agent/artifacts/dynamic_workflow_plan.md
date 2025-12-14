# 动态工作流可视化实现计划

## 目标
实现一个动态的、支持并行 Agent 嵌套展示的批改工作流可视化系统。

## 当前状态
- 后端 `/batch/submit` 只返回 batch_id，不触发实际批改
- 前端工作流是固定的 6 个节点
- WebSocket 连接建立但没有消息推送

## 需求分解

### 1. 后端改造
- [ ] 修改 `/batch/submit` 端点，启动实际批改流程
- [ ] 实现 WebSocket 实时推送：
  - 工作流节点状态变化
  - 并行 Agent 数量和状态
  - 每个 Agent 的日志和输出

### 2. 前端改造

#### 2.1 数据结构
```typescript
interface WorkflowNode {
  id: string;
  label: string;
  type: 'sequential' | 'parallel-container' | 'parallel-child';
  status: 'pending' | 'running' | 'completed' | 'failed';
  parentId?: string;  // 用于并行子节点
  children?: WorkflowNode[];  // 用于并行容器
  logs?: string[];
  output?: any;
  progress?: number;
}
```

#### 2.2 WorkflowGraph 组件改造
- 支持动态节点数量
- 并行容器节点：
  - 显示为大方块
  - 内部可滚动
  - 嵌套显示子 Agent
- 每个子 Agent 可点击

#### 2.3 NodeInspector 组件改造
- 支持显示并行子节点详情
- Slide-in 面板而非弹窗
- 显示实时日志流

### 3. 实现步骤

#### Phase 1: 后端实时推送（模拟）
1. 修改 submit 端点，启动后台任务
2. 后台任务通过 WebSocket 推送进度
3. 模拟多个并行批改 Agent

#### Phase 2: 前端动态工作流
1. 重构 consoleStore 数据结构
2. 改造 WorkflowGraph 支持动态节点
3. 实现并行 Agent 容器组件
4. 改造 NodeInspector 支持嵌套

#### Phase 3: 集成测试
1. 端到端测试文件上传
2. 验证 WebSocket 消息接收
3. 验证 UI 动态更新

## 关键技术决策
1. **WebSocket 消息格式**：使用 JSON，包含 type、nodeId、status、data
2. **并行容器布局**：使用 CSS Grid + overflow-y: auto
3. **动画**：使用 Framer Motion 实现平滑过渡
4. **状态管理**：Zustand + immer 处理嵌套更新

## 文件变更清单
- `src/api/routes/batch.py` - 后端批改逻辑
- `src/store/consoleStore.ts` - 状态结构改造
- `src/components/console/WorkflowGraph.tsx` - 动态工作流
- `src/components/console/ParallelAgentContainer.tsx` - 新增并行容器
- `src/components/console/NodeInspector.tsx` - 详情面板改造
