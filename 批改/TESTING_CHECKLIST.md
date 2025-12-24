# 批改系统测试清单

## 测试环境
- 后端：http://127.0.0.1:8001 ✅ 运行中
- 前端：http://localhost:3000 ✅ 运行中
- 数据库：离线模式（PostgreSQL/Redis 未连接）
- 模型：gemini-3-flash-preview

## 核心要求验证

### 1. 评分标准解析 ✅ 已修复
- [x] 使用 `RubricParserService` 替代简单的 `analyze_with_vision`
- [x] 支持分批处理（每批最多 4 页）
- [ ] **待测试**：上传测试文件，验证是否识别出 19 道题、105 分

### 2. 批改结果透明度
- [x] 后端发送 `rubric_parsed` 事件（包含完整题目列表）
- [x] 后端发送 `page_graded` 事件（每页批改完成）
- [x] 后端发送 `grading_progress` 事件（批改进度）
- [x] 后端发送 `students_identified` 事件（学生识别结果）
- [x] 前端监听所有事件并显示
- [ ] **待测试**：前端是否正确显示所有模块输出

### 3. 数据正确传输
- [x] 后端 `_format_results_for_frontend` 格式化学生结果
- [x] 前端 `StudentResult` 接口定义
- [x] WebSocket 事件传输
- [ ] **待测试**：前端显示的分数是否与后端日志一致

### 4. 批次进度显示
- [x] 后端在 `grade_batch_node` 中记录批次信息
- [x] 后端发送 `batch_completed` 事件
- [x] 前端监听 `batch_completed` 事件
- [ ] **待测试**：前端是否显示 "批次 1/10" 等进度信息

### 5. 学生识别顺序 ✅ 已实现
- [x] 工作流：intake → preprocess → rubric_parse → grade_batch → segment → review → export
- [x] `segment_node` 在批改后执行
- [x] 使用 `StudentBoundaryDetector` 基于批改结果识别学生

## 测试步骤

1. 打开前端 http://localhost:3000
2. 上传测试文件：
   - 评分标准：`批改标准.pdf`
   - 学生作答：`学生作答.pdf`
3. 观察前端控制台和工作流节点状态
4. 检查以下内容：
   - 评分标准解析结果（应显示 19 题、105 分）
   - 批改进度更新（应显示批次进度）
   - 最终结果（分数、学生数）

## 已知问题

1. ~~评分标准解析不完整~~ ✅ 已修复（使用 RubricParserService）
2. ~~前端事件名称不一致~~ ✅ 已修复（student_identified → students_identified）
3. ~~缺少辅助函数~~ ✅ 已修复（添加了所有缺失的函数）

## 下一步

等待用户上传测试文件并反馈结果。
