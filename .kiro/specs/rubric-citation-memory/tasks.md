# 评分标准引用与记忆系统优化 - 任务列表

## 任务概览

- **总任务数**: 12
- **预计工时**: 8-10 小时
- **依赖关系**: 任务 1-3 可并行，任务 4-6 依赖 1-3，任务 7-9 依赖 4-6

---

## 第一阶段：数据模型扩展

### 1. 扩展 ScoringPointResult 数据模型
- [x] 1.1 在 `grading_models.py` 中添加新字段
  - 添加 `rubric_reference: Optional[str]`
  - 添加 `is_alternative_solution: bool`
  - 添加 `alternative_description: str`
  - 添加 `point_confidence: float`
  - 添加 `citation_quality: str` (exact/partial/none)
- [x] 1.2 更新 `to_dict()` 和 `from_dict()` 方法
- [ ] 1.3 添加单元测试验证序列化/反序列化

### 2. 扩展 MemoryEntry 数据模型
- [x] 2.1 在 `grading_memory.py` 中添加 `MemoryVerificationStatus` 枚举
- [x] 2.2 添加新字段到 `MemoryEntry`
  - 添加 `verification_status: MemoryVerificationStatus`
  - 添加 `verification_history: List[Dict]`
  - 添加 `source_self_report_id: Optional[str]`
  - 添加 `is_soft_deleted: bool`
  - 添加 `deleted_at: Optional[str]`
  - 添加 `deleted_reason: Optional[str]`
- [x] 2.3 更新 `to_dict()` 和 `from_dict()` 方法
- [ ] 2.4 添加单元测试

---

## 第二阶段：置信度计算服务

### 3. 创建置信度计算服务
- [x] 3.1 创建 `src/services/confidence_calculator.py`
- [x] 3.2 实现 `calculate_point_confidence()` 函数
  - 有精确引用：base 0.9
  - 部分引用：base * 0.9
  - 无引用：min(base, 0.7)
  - 另类解法：再降 25%
- [x] 3.3 实现 `calculate_question_confidence()` 函数（加权平均）
- [x] 3.4 实现 `calculate_student_confidence()` 函数
- [ ] 3.5 编写属性测试验证 P1（置信度计算正确性）

---

## 第三阶段：LLM Prompt 更新

### 4. 更新评分映射 Prompt
- [x] 4.1 修改 `llm_reasoning.py` 中的评分 prompt
  - 强制要求输出 `rubric_reference`
  - 添加 `citation_quality` 字段
  - 添加 `is_alternative_solution` 字段
- [x] 4.2 更新 `_normalize_question_detail()` 解析新字段
- [ ] 4.3 集成置信度计算服务
- [ ] 4.4 添加集成测试验证 prompt 输出格式

---

## 第四阶段：记忆系统增强

### 5. 实现记忆验证机制
- [x] 5.1 添加 `verify_memory()` 方法
- [x] 5.2 添加 `promote_to_core()` 方法
- [x] 5.3 添加 `mark_suspicious()` 方法
- [x] 5.4 实现状态转换验证（P2）
- [ ] 5.5 编写属性测试验证状态转换正确性

### 6. 实现记忆软删除和回滚
- [x] 6.1 添加 `soft_delete_memory()` 方法
- [x] 6.2 添加 `rollback_memory()` 方法
- [x] 6.3 更新 `retrieve_relevant_memories()` 排除已删除记忆
- [ ] 6.4 添加单元测试

---

## 第五阶段：自白-记忆集成

### 7. 实现自白驱动的记忆更新
- [ ] 7.1 扩展 `SelfReportIssue` 数据结构
- [ ] 7.2 实现 `update_memory_from_self_report()` 函数
- [ ] 7.3 在 `generate_self_report()` 中标记需要创建记忆的问题
- [ ] 7.4 添加 `memory_updates` 到自白输出
- [ ] 7.5 编写属性测试验证 P4（自白-记忆一致性）

### 8. 实现记忆审查机制
- [ ] 8.1 实现 `review_memory_conflict()` 函数
- [ ] 8.2 在逻辑复核后调用记忆审查
- [ ] 8.3 记录审查结果到记忆条目
- [ ] 8.4 添加单元测试

---

## 第六阶段：逻辑复核独立性

### 9. 确保逻辑复核独立性
- [ ] 9.1 审查 `logic_review` 相关函数，移除记忆依赖
- [ ] 9.2 添加代码注释说明独立性要求
- [ ] 9.3 编写属性测试验证 P3（逻辑复核独立性）

---

## 第七阶段：API 接口

### 10. 创建记忆管理 API
- [ ] 10.1 创建 `src/api/routes/memory_api.py`
- [ ] 10.2 实现 `GET /api/memory/stats` 统计接口
- [ ] 10.3 实现 `GET /api/memory/list` 查询接口
- [ ] 10.4 实现 `POST /api/memory/{id}/verify` 验证接口
- [ ] 10.5 实现 `DELETE /api/memory/{id}` 软删除接口
- [ ] 10.6 实现 `POST /api/memory/{id}/rollback` 回滚接口
- [ ] 10.7 注册路由到 `main.py`

### 11. 增强自白 API
- [ ] 11.1 更新 `GET /api/grading/{batch_id}/self-report` 返回格式
- [ ] 11.2 添加 `memory_updates` 字段
- [ ] 11.3 添加 API 文档

---

## 第八阶段：测试与文档

### 12. 综合测试与文档
- [ ] 12.1 编写端到端测试
- [ ] 12.2 更新 API 文档
- [ ] 12.3 更新 README 说明新功能
- [ ] 12.4 添加使用示例

---

## 属性测试清单

| 属性 | 描述 | 测试文件 |
|------|------|----------|
| P1 | 置信度计算正确性 | `test_confidence_calculator.py` |
| P2 | 记忆状态转换正确性 | `test_memory_verification.py` |
| P3 | 逻辑复核独立性 | `test_logic_review_independence.py` |
| P4 | 自白-记忆一致性 | `test_self_report_memory.py` |
