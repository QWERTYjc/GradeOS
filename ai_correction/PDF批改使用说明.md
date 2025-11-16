# PDF批改脚本使用说明

## 概述

`batch_correct_pdfs.py` 是一个使用LangGraph工作流进行PDF批改的脚本，支持实时追踪批改进度和问题。

## 功能特性

✅ **实时进度追踪**: 显示批改过程中的每个步骤和进度百分比  
✅ **错误监控**: 自动记录和报告批改过程中出现的错误  
✅ **警告提示**: 记录可能影响批改质量的问题  
✅ **详细日志**: 保存完整的批改日志和结果  
✅ **多模态支持**: 支持文本PDF和扫描版PDF（需要Vision API）

## 使用方法

### 1. 准备文件

将以下文件放在项目根目录：
- `学生作答.pdf` - 学生答案文件
- `批改标准.pdf` - 评分标准文件（可选）

### 2. 配置API密钥

在项目根目录创建 `.env` 文件，添加：

```bash
OPENROUTER_API_KEY=your-api-key-here
# 或者
LLM_API_KEY=your-api-key-here
```

### 3. 运行批改脚本

```bash
cd ai_correction
python batch_correct_pdfs.py
```

## 输出结果

脚本会在 `correction_results` 目录下生成：

1. **JSON结果文件** (`correction_result_YYYYMMDD_HHMMSS.json`)
   - 完整的批改结果数据
   - 包含进度历史、错误、警告等详细信息

2. **文本结果文件** (`correction_result_YYYYMMDD_HHMMSS.txt`)
   - 人类可读的批改结果
   - 包含得分、等级、详细反馈等

3. **日志文件** (`batch_correction.log`)
   - 详细的执行日志

## 当前已知问题

### 1. API认证失败 (401错误)

**问题**: OpenRouter API返回401未授权错误

**原因**: 
- API密钥未配置或无效
- 环境变量未正确加载

**解决方案**:
1. 检查 `.env` 文件是否存在并包含正确的API密钥
2. 确认API密钥有效（可以在OpenRouter网站验证）
3. 确保使用 `python-dotenv` 加载环境变量

### 2. LangGraph并发更新错误

**问题**: `Can receive only one value per step`

**原因**: LangGraph工作流中多个节点并行更新同一个状态键

**当前状态**: 已修复监控函数，使用 `stream_mode='values'` 避免并发问题

### 3. 扫描版PDF处理

**问题**: 批改标准PDF是扫描版，无法提取文本

**警告信息**: `批改标准PDF可能是扫描版，将使用Vision API处理`

**解决方案**:
1. **推荐**: 使用文本版PDF或转换为文本文件
2. **备选**: 安装 `pdf2image` 库将PDF转换为图片
   ```bash
   pip install pdf2image poppler-utils
   ```

## 批改流程

脚本执行以下步骤：

1. **文件验证** (5%)
   - 检查文件是否存在
   - 验证文件格式

2. **文件处理** (10-40%)
   - 处理题目PDF
   - 处理学生作答PDF
   - 处理批改标准PDF（如果提供）

3. **工作流初始化** (50%)
   - 创建任务ID
   - 初始化LangGraph工作流

4. **工作流执行** (55-95%)
   - 任务编排
   - 多模态文件处理
   - 并行理解（题目/答案/评分标准）
   - 学生识别
   - 批次规划
   - 批改执行
   - 结果聚合

5. **完成** (100%)
   - 生成最终报告
   - 保存结果文件

## 工作流架构

脚本使用LangGraph多模态工作流，包含以下Agent：

1. **OrchestratorAgent** - 任务编排
2. **MultiModalInputAgent** - 多模态文件处理
3. **QuestionUnderstandingAgent** - 题目理解
4. **AnswerUnderstandingAgent** - 答案理解
5. **RubricInterpreterAgent** - 评分标准解析
6. **StudentDetectionAgent** - 学生识别
7. **BatchPlanningAgent** - 批次规划
8. **RubricMasterAgent** - 评分标准主控
9. **QuestionContextAgent** - 题目上下文
10. **GradingWorkerAgent** - 批改工作
11. **ResultAggregatorAgent** - 结果聚合
12. **ClassAnalysisAgent** - 班级分析

## 结果格式

### JSON结果结构

```json
{
  "task_id": "pdf_correction_20251114_213351",
  "status": "completed",
  "total_score": 85.0,
  "grade_level": "B",
  "detailed_feedback": [...],
  "criteria_evaluations": [...],
  "errors": [...],
  "warnings": [...],
  "tracking": {
    "progress_history": [...],
    "errors": [...],
    "warnings": [...],
    "duration_seconds": 123.45
  }
}
```

### 文本结果示例

```
================================================================================
PDF批改结果
================================================================================

任务ID: pdf_correction_20251114_213351
状态: completed
总分: 85.0
等级: B

详细反馈:
--------------------------------------------------------------------------------
1. 答案基本正确，但存在一些计算错误
2. 解题思路清晰，步骤完整
...

错误和警告
================================================================================

错误:
  无错误

警告:
  1. [文件处理] 批改标准PDF可能是扫描版，将使用Vision API处理
```

## 故障排查

### 问题1: 脚本无法运行

**检查**:
- Python版本 >= 3.8
- 已安装所有依赖: `pip install -r requirements.txt`
- 文件路径正确

### 问题2: API调用失败

**检查**:
- API密钥是否正确配置
- 网络连接是否正常
- API配额是否充足

### 问题3: PDF处理失败

**检查**:
- PDF文件是否损坏
- 是否安装了必要的PDF处理库（PyPDF2）
- 扫描版PDF需要安装pdf2image

## 下一步改进

1. ✅ 修复并发更新错误
2. ⏳ 改进错误处理和重试机制
3. ⏳ 添加PDF预览功能
4. ⏳ 支持批量处理多个学生作业
5. ⏳ 优化扫描版PDF处理流程

## 联系支持

如遇到问题，请检查：
1. 日志文件 `batch_correction.log`
2. 结果文件中的错误信息
3. 控制台输出的警告和错误

## 更新日志

### 2025-11-14
- ✅ 创建初始批改脚本
- ✅ 添加实时进度追踪
- ✅ 添加错误和警告记录
- ✅ 修复并发更新错误
- ✅ 添加API密钥检查
- ⚠️ 已知问题：API认证需要配置


