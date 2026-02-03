# 批改和审计一体化改造总结

## 改造日期
2026-02-03

## 改造目标
根据 backend-architect 的设计方案，将批改（grading）和审计（audit）功能合并为一体，移除独立的 confession 节点，在批改过程中直接生成审计信息。

## 核心改动

### 1. 移除 Confession 节点 ✅

**删除的文件：**
- `backend/src/services/grading_confession.py` - 完整删除

**删除的函数：**
- `backend/src/graphs/batch_grading.py`:
  - `_extract_confession_questions()` - 第 3960 行
  - `_build_confession_prompt()` - 第 4067-4305 行
  - `confession_node()` - 第 4118-4414 行

**更新的工作流图：**
- 移除 `confession` 节点的添加：`graph.add_node("confession", confession_node)`
- 更新边连接：`grade_batch → logic_review`（原 `grade_batch → confession → logic_review`）
- 更新路由器：移除 `confession` 分支

**清理的导入：**
- `backend/src/services/__init__.py` - 移除 `generate_confession` 导入和导出

### 2. 修改批改节点（Grade Batch）✅

**文件：** `backend/src/services/llm_reasoning.py`

**修改内容：**

1. **更新提示词 `_build_grading_prompt()`（第 921 行）**
   - 在输出 JSON 格式中添加 `audit` 字段要求
   - 每道题的 `question_details` 必须包含：
     ```json
     "audit": {
       "confidence": 0.85,
       "uncertainties": ["符号可能识别不清"],
       "risk_flags": ["formula_ambiguity"],
       "needs_review": false
     }
     ```
   
2. **审计字段说明：**
   - **confidence** (float, 0-1): 批改置信度
   - **uncertainties** (list[str]): 不确定点列表（每条≤50字）
   - **risk_flags** (list[str]): 风险标签
     - full_marks: 满分风险
     - zero_marks: 零分风险
     - boundary_score: 边界分数
     - low_confidence: 低置信度
     - evidence_gap: 证据不足
     - formula_ambiguity: 公式识别模糊
     - alternative_solution: 另类解法
   - **needs_review** (bool): 是否需要人工复核

3. **更新响应解析 `_parse_grading_response()`（第 991 行）**
   - 添加 audit 字段的自动生成逻辑
   - 为缺失 audit 的题目自动生成默认 audit 信息
   - 基于评分情况自动标记风险（满分、零分、低置信度、空证据）

4. **更新文本批改提示词 `_build_text_grading_prompt()`（第 1143 行）**
   - 同样添加 audit 字段要求到输出格式中

### 3. 修改逻辑复核节点（Logic Review）✅

**文件：** `backend/src/graphs/batch_grading.py`

**修改内容：**

1. **更新 `_extract_logic_review_questions()`（第 3963 行）**
   - 移除对 `confession` 数据的依赖
   - 改为基于题目的 `audit` 信息筛选需要复核的题目
   - 筛选逻辑：
     - `audit.needs_review == true`
     - `audit.confidence < 0.7`
     - `audit.risk_flags` 包含高风险标记
     - `audit.uncertainties` 不为空

2. **更新 `_build_logic_review_prompt()`（第 4108 行）**
   - 移除 `confession` 参数
   - 添加基于 `audit` 信息的风险摘要部分
   - 提示词中展示：
     - 需要复核题目数
     - 低置信度题目数
     - 高风险题目数
     - 具体风险标记

3. **更新 `logic_review_node()` 调用**
   - 移除对 `confessed_results` 的引用
   - 直接使用 `student_results`
   - 移除 `confession` 参数传递

### 4. 数据库迁移 ✅

**新增文件：** `backend/alembic/versions/2026_02_03_1400-add_audit_fields.py`

**迁移内容：**

1. **批次汇总字段（grading_history 表）：**
   ```sql
   ALTER TABLE grading_history
   ADD COLUMN IF NOT EXISTS questions_need_review INTEGER DEFAULT 0,
   ADD COLUMN IF NOT EXISTS avg_confidence DECIMAL(3, 2) DEFAULT 1.0,
   ADD COLUMN IF NOT EXISTS high_risk_count INTEGER DEFAULT 0;
   ```

2. **索引优化：**
   - `idx_question_details_needs_review` - 为 JSONB 中的 audit.needs_review 创建 GIN 索引
   - `idx_grading_history_needs_review` - 批次需复核数索引
   - `idx_grading_history_avg_confidence` - 批次平均置信度索引

**说明：**
- 题目级别的 audit 信息存储在 `question_details` JSONB 字段中
- 不需要单独的列，PostgreSQL 支持 JSONB 查询和索引

### 5. API 路由更新 ✅

**文件：** `backend/src/api/routes/batch_langgraph.py`

**修改内容：**

1. **`get_batch_results()` API（第 3004 行）**
   - 移除对 `confessed_results` 的引用
   - 简化结果获取逻辑：`reviewed_results` or `student_results`
   - audit 字段会自动包含在返回的 question_details 中

2. **清理 confession 相关代码：**
   - 移除 `confession_payload` 的读取和传递
   - audit 信息已嵌入在 question_details 中，无需额外处理

### 6. 文档更新 ✅

**文件：** `backend/src/graphs/batch_grading.py`

**更新内容：**
- 工作流图文档注释（第 6060 行）
- 移除 confession 节点的描述
- 更新流程图，反映新的工作流

## 向后兼容性

### 数据兼容
- 旧的批改结果如果没有 audit 字段，会在响应解析时自动生成默认值
- 默认 audit 值：
  ```json
  {
    "confidence": 0.7,
    "uncertainties": [],
    "risk_flags": [],
    "needs_review": false
  }
  ```

### API 兼容
- API 返回的数据结构保持不变，只是去除了 `confession` 字段
- 新增的 `audit` 字段嵌套在 `question_details` 中
- 前端可以逐步适配新的 audit 字段

## 测试建议

### 单元测试
1. 测试 `_parse_grading_response()` 自动生成 audit 逻辑
2. 测试 `_extract_logic_review_questions()` 基于 audit 的筛选逻辑
3. 测试向后兼容：缺失 audit 字段时的默认值生成

### 集成测试
1. 完整的批改流程测试（含 audit 生成）
2. 逻辑复核节点基于 audit 信息的复核测试
3. API 返回数据格式测试

### 端到端测试
1. 提交批改请求
2. 验证返回结果包含 audit 字段
3. 验证高风险题目被正确标记为 `needs_review=true`
4. 验证逻辑复核优先处理高风险题目

## 部署步骤

### 1. 运行数据库迁移
```bash
cd backend
alembic upgrade head
```

### 2. 验证迁移
```bash
# 检查 grading_history 表是否有新字段
psql -d your_database -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'grading_history' AND column_name IN ('questions_need_review', 'avg_confidence', 'high_risk_count');"
```

### 3. 重启后端服务
```bash
# 确保使用最新代码
git pull
# 重启服务（根据部署方式）
# Railway 会自动检测并部署
```

### 4. 验证功能
- 提交新的批改任务
- 检查返回结果是否包含 audit 字段
- 检查逻辑复核是否基于 audit 信息工作

## 性能优化

### 已实施
1. **JSONB 索引** - 为 audit.needs_review 创建 GIN 索引，优化查询
2. **部分索引** - 只对需要复核的批次和低置信度批次创建索引
3. **批次汇总** - 在批次级别存储汇总统计，避免每次聚合查询

### 未来优化
1. **缓存热点数据** - 缓存需要复核的批次列表
2. **异步统计** - 批次完成后异步计算汇总统计
3. **分页优化** - 大批次结果的分页加载

## 监控指标

### 关键指标
1. **audit 字段覆盖率** - 批改结果中 audit 字段的完整性
2. **needs_review 比例** - 需要人工复核的题目占比
3. **平均置信度** - 批改结果的平均置信度
4. **高风险题目数** - 标记为高风险的题目数量

### 告警阈值（建议）
- `needs_review` 比例 > 30% → 可能批改质量下降
- `avg_confidence` < 0.6 → 批改不确定性高
- `high_risk_count` > 批次题目数 * 0.4 → 异常高风险

## 已知问题和限制

### 当前限制
1. **LLM 输出一致性** - LLM 可能不总是输出完整的 audit 字段
   - **缓解措施**：响应解析时自动生成默认值
   
2. **风险标记准确性** - 依赖 LLM 对风险的判断
   - **缓解措施**：启发式规则补充（满分、零分、低置信度自动标记）

3. **旧数据兼容** - 历史批改结果没有 audit 字段
   - **缓解措施**：查询时提供默认值

### 未来改进
1. **风险模型训练** - 基于人工复核反馈训练风险预测模型
2. **自适应阈值** - 根据历史数据动态调整置信度阈值
3. **批量回填** - 为历史数据生成 audit 信息

## 总结

本次改造成功实现了批改和审计的一体化，主要成果：

✅ **简化工作流** - 移除 confession 节点，减少延迟
✅ **提高效率** - 批改时同步生成审计信息，减少重复推理
✅ **增强可维护性** - 审计信息结构化存储，便于查询和分析
✅ **优化性能** - 添加索引，优化查询性能
✅ **保持兼容** - 向后兼容旧数据，平滑过渡

## 相关文档

- 设计方案：由 backend-architect 提供
- 数据库迁移：`backend/alembic/versions/2026_02_03_1400-add_audit_fields.py`
- API 文档：待更新（需要添加 audit 字段说明）

## 联系人

- 开发者：AI Agent (repository-optimizer)
- 审核者：待指定
- 测试负责人：待指定
