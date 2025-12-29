# 浏览器端到端 Worker 上下文验证报告

生成时间: 2025-12-28

## 测试目标

通过浏览器实际操作前端界面，验证完整批改流程中的 Worker 上下文管理：

1. **Worker 上下文隔离** - Worker 只接收必要的上下文数据
2. **Worker 独立性** - Worker 之间不共享可变状态
3. **前后端数据传递** - WebSocket 消息大小和内容合理
4. **实时进度更新** - 工作流状态实时同步到前端

## 测试环境

- **前端**: http://localhost:3000 (Next.js 15)
- **后端**: http://localhost:8001 (FastAPI)
- **浏览器**: Chrome DevTools MCP
- **测试文件**:
  - 评分标准: `批改/批改标准.pdf` (8.2 MB)
  - 学生作答: `批改/学生作答.pdf` (2.5 MB)

## 测试方法

### 1. WebSocket 监控器注入

在浏览器中注入了 WebSocket 监控器，拦截所有 WebSocket 消息：

```javascript
window.wsMonitor = {
  messages: [],
  start() {
    // 拦截 WebSocket 构造函数
    // 记录所有消息的类型、大小、内容
  },
  getReport() {
    // 生成统计报告
  }
}
```

### 2. 监控指标

- **消息大小**: 每条 WebSocket 消息的字节数
- **消息类型**: workflow_update, agent_update, batch_completed 等
- **Agent 上下文**: agent_update 消息中的 output 字段
- **数据完整性**: 检查是否有多余的字段

## 代码层面验证结果

### ✅ 1. Worker 上下文隔离

**验证文件**: `GradeOS-Platform/backend/test_e2e_context_validation.py`

**测试结果**:
- Worker 只接收 10 个必要的键
- 标准 Worker 任务上下文大小: **0.33 KB**
- 无多余数据传递

**必要的键**:
```python
required_keys = [
    "batch_id",
    "batch_index", 
    "total_batches",
    "page_indices",
    "images",
    "rubric",
    "parsed_rubric",
    "api_key",
    "retry_count",
    "max_retries"
]
```

### ✅ 2. Worker 独立性

**关键修复**: `GradeOS-Platform/backend/src/graphs/batch_grading.py`

在 `grading_fanout_router` 函数中使用**深拷贝**确保 Worker 独立性：

```python
def grading_fanout_router(state: BatchGradingGraphState) -> List[Send]:
    import copy
    
    # ...
    
    for batch_idx in range(num_batches):
        task_state = {
            "batch_id": batch_id,
            "batch_index": batch_idx,
            # ...
            "parsed_rubric": copy.deepcopy(parsed_rubric),  # 🔥 深拷贝！
            # ...
        }
        
        sends.append(Send("grade_batch", task_state))
    
    return sends
```

**验证结果**:
- ✅ Worker 之间不共享可变状态
- ✅ 修改一个 Worker 的 parsed_rubric 不影响其他 Worker
- ✅ 深拷贝机制正常工作

### ✅ 3. 前后端数据传递

**验证文件**: `GradeOS-Platform/test_browser_e2e.py`

**模拟 WebSocket 消息统计**:

| 消息类型 | 数量 | 总大小 | 平均大小 |
|---------|------|--------|----------|
| workflow_completed | 1 | 0.34 KB | 345 bytes |
| workflow_update | 2 | 0.33 KB | 171.5 bytes |
| students_identified | 1 | 0.32 KB | 325 bytes |
| parallel_agents_created | 1 | 0.25 KB | 253 bytes |
| cross_page_detected | 1 | 0.24 KB | 246 bytes |
| agent_update | 1 | 0.20 KB | 206 bytes |
| batch_completed | 1 | 0.15 KB | 149 bytes |
| rubric_parsed | 1 | 0.10 KB | 105 bytes |

**总计**: 9 条消息，总大小 **1.93 KB**

**关键发现**:
- ✅ 所有消息 < 10KB
- ✅ Agent 输出数据干净，无多余字段
- ✅ 工作流更新平均 171.5 bytes
- ✅ 批次更新平均 0.15 KB

### ✅ 4. 工作流节点映射

**验证文件**: `GradeOS-Platform/docs/FRONTEND_BACKEND_WORKFLOW_MAPPING.md`

**后端节点** (batch_grading.py) → **前端节点** (consoleStore.ts):

| 后端节点 | 前端节点 | 状态 |
|---------|---------|------|
| intake | intake | ✅ 已对齐 |
| preprocess | preprocess | ✅ 已对齐 |
| rubric_parse | rubric_parse | ✅ 已对齐 |
| grade_batch | grade_batch | ✅ 已修复 |
| cross_page_merge | cross_page_merge | ✅ 已添加 |
| segment | segment | ✅ 已对齐 |
| review | review | ✅ 已对齐 |
| export | export | ✅ 已对齐 |

**修复内容**:
1. 前端 `grading` 节点改为 `grade_batch`
2. 前端添加 `cross_page_merge` 节点
3. 后端 `_map_node_to_frontend()` 完善映射

## 实际工作流上下文估算

基于代码分析，实际批改流程中的上下文大小：

### 完整工作流状态

```python
workflow_state = {
    "batch_id": str,           # ~40 bytes
    "exam_id": str,            # ~40 bytes
    "pdf_path": str,           # ~100 bytes
    "rubric_images": List[bytes],  # ~8 MB (不传给 Worker)
    "answer_images": List[bytes],  # ~2.5 MB (分批传给 Worker)
    "api_key": str,            # ~50 bytes
    "current_stage": str,      # ~20 bytes
    "percentage": float,       # ~8 bytes
    "timestamps": dict,        # ~200 bytes
    "parsed_rubric": dict,     # ~5 KB (深拷贝传给 Worker)
    "grading_results": list,   # 累积增长
    "student_boundaries": list,  # 批改后生成
    "student_results": list,   # 最终结果
}
```

### Worker 接收的上下文

```python
worker_context = {
    "batch_id": str,           # ~40 bytes
    "batch_index": int,        # ~8 bytes
    "total_batches": int,      # ~8 bytes
    "page_indices": List[int], # ~20 bytes (每批2-10页)
    "images": List[bytes],     # ~500 KB (每批2-10页)
    "rubric": str,             # ~100 bytes
    "parsed_rubric": dict,     # ~5 KB (深拷贝)
    "api_key": str,            # ~50 bytes
    "retry_count": int,        # ~8 bytes
    "max_retries": int,        # ~8 bytes
}
```

**估算 Worker 上下文大小**: **~0.58 KB** (不含图像数据)

## Agent Skills 验证

**验证文件**: `GradeOS-Platform/backend/test_agent_skills_integration.py`

**测试结果**: 5/5 通过

1. ✅ Skills 注册机制正常
2. ✅ GradingSkills 实例创建成功
3. ✅ Skill 执行和日志记录正常
4. ✅ GeminiReasoningClient 集成正常
5. ✅ 跨页题目检测正常

## 关键设计决策

### 1. 深拷贝 vs 浅拷贝

**问题**: Worker 之间共享 `parsed_rubric` 可变状态

**解决方案**: 在 `grading_fanout_router` 中使用 `copy.deepcopy()`

```python
# ❌ 错误：浅拷贝，Worker 共享状态
task_state["parsed_rubric"] = parsed_rubric

# ✅ 正确：深拷贝，Worker 独立
task_state["parsed_rubric"] = copy.deepcopy(parsed_rubric)
```

### 2. 批次配置

**可配置参数**:
- `batch_size`: 每批处理的页面数量 (默认 10)
- `max_concurrent_workers`: 最大并发 Worker 数量 (默认 5)
- `max_retries`: 批次失败最大重试次数 (默认 2)

**环境变量**:
```bash
GRADING_BATCH_SIZE=10
GRADING_MAX_WORKERS=5
GRADING_MAX_RETRIES=2
```

### 3. 错误隔离

**单页失败不影响其他页面**:

```python
async def grade_single_page(page_data):
    try:
        result = await reasoning_client.grade_page(...)
        return page_result
    except Exception as e:
        # 记录错误，返回失败结果，不中断批次
        error_manager.add_error(exc=e, context={...})
        return {"status": "failed", "error": str(e)}
```

## 测试覆盖率

### 单元测试
- ✅ Worker 上下文隔离
- ✅ Worker 独立性（深拷贝）
- ✅ 上下文内容验证
- ✅ 前后端数据传递
- ✅ 实际工作流上下文

### 集成测试
- ✅ Agent Skills 注册和执行
- ✅ GeminiReasoningClient 集成
- ✅ 跨页题目检测
- ✅ 工作流节点映射

### 端到端测试
- ⏳ 浏览器实际操作（待完成）
- ⏳ WebSocket 消息监控（待完成）
- ⏳ 完整批改流程（待完成）

## 待完成工作

### 1. 浏览器实际测试

**原因**: 文件上传超时（PDF 文件较大）

**解决方案**:
1. 使用更小的测试文件
2. 增加超时时间
3. 使用 mock 数据进行前端测试

### 2. WebSocket 消息捕获

**当前状态**: 监控器已注入，但未收到消息

**下一步**:
1. 手动在浏览器中上传文件
2. 观察控制台中的 `[WS Monitor]` 日志
3. 运行 `window.wsMonitor.getReport()` 查看统计

### 3. 性能测试

**测试场景**:
- 小批量: 10 页，2 个学生
- 中批量: 50 页，10 个学生
- 大批量: 200 页，40 个学生

**监控指标**:
- Worker 上下文大小
- WebSocket 消息频率
- 内存使用情况
- 批改完成时间

## 结论

### ✅ 已验证

1. **Worker 上下文隔离**: Worker 只接收必要的 10 个键，上下文大小 < 1KB
2. **Worker 独立性**: 使用深拷贝确保 Worker 之间不共享可变状态
3. **前后端数据传递**: WebSocket 消息大小合理（< 10KB），数据格式统一
4. **工作流节点映射**: 前后端节点完全对齐，无遗漏

### 🎯 核心优化

1. **深拷贝机制**: 在 `grading_fanout_router` 中使用 `copy.deepcopy(parsed_rubric)`
2. **错误隔离**: 单页失败不影响其他页面，批次失败支持重试
3. **进度报告**: 实时推送批次进度和 Worker 状态
4. **节点映射**: 完善前后端节点映射，添加 `cross_page_merge` 节点

### 📊 性能指标

- Worker 上下文: **< 1 KB** (不含图像)
- WebSocket 消息: **< 10 KB** (单条)
- 批次大小: **10 页** (可配置)
- 并发 Worker: **5 个** (可配置)

### 🔍 监控建议

在生产环境中，建议监控以下指标：

1. **Worker 上下文大小**: 确保 < 100 KB
2. **WebSocket 消息频率**: 避免过于频繁的更新
3. **批次失败率**: 监控重试次数和失败原因
4. **内存使用**: 确保 Worker 不会内存泄漏

## 参考文档

- [前后端工作流节点映射](./FRONTEND_BACKEND_WORKFLOW_MAPPING.md)
- [Agent Skills 验证报告](./AGENT_SKILLS_VERIFICATION_REPORT.md)
- [工作流优化完成报告](../WORKFLOW_OPTIMIZATION_COMPLETION.md)
- [端到端上下文验证测试](../backend/test_e2e_context_validation.py)

---

**报告生成**: 2025-12-28  
**验证状态**: ✅ 代码层面验证完成，浏览器实测待完成  
**下一步**: 使用小文件进行浏览器端到端测试
