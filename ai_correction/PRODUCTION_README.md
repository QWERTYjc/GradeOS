# 🎓 生产级 AI 批改系统 - 使用指南

## 📋 目录
- [系统概述](#系统概述)
- [快速开始](#快速开始)
- [功能特点](#功能特点)
- [安装部署](#安装部署)
- [使用说明](#使用说明)
- [注意事项](#注意事项)
- [常见问题](#常见问题)

---

## 🎯 系统概述

这是一个**生产级的 AI 批改系统**，基于 LangGraph 构建，提供：

- ✅ **逐题批改**：精确定位每道题的错误
- ✅ **多维度分析**：学生、班级、知识点、题型统计
- ✅ **数据持久化**：自动保存到 PostgreSQL/MySQL 数据库
- ✅ **流式处理**：实时反馈批改进度
- ✅ **智能策略**：根据题型自动选择批改方法

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd ai_correction
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
# 使用 PostgreSQL（推荐）
export DATABASE_TYPE=postgresql
export DATABASE_URL="postgresql://user:password@localhost:5432/ai_correction"

# 或使用 MySQL
export DATABASE_TYPE=mysql
export DATABASE_URL="mysql://user:password@localhost:3306/ai_correction"

# 或使用 JSON 文件（开发环境）
export DATABASE_TYPE=json

# 初始化数据库
python init_database.py --test
```

### 3. 运行测试

```bash
python test_production_grading.py
```

### 4. 启动应用

```bash
streamlit run streamlit_simple.py
```

---

## ✨ 功能特点

### 1. 逐题批改

系统会**逐题分析**每道题目，而不是整体批改：

- 识别题型（选择题、填空题、解答题、计算题）
- 分析难度（简单、中等、困难）
- 选择批改策略（关键词匹配、语义理解、评分标准、步骤分析）
- 生成详细反馈

### 2. 多维度数据分析

#### 学生维度
- 总分、得分率、等级
- 答对题数、错误题数
- 知识点掌握情况
- 历史成绩趋势

#### 班级维度
- 平均分、最高分、最低分
- 题型得分率
- 难度得分率
- 知识点掌握率

#### 题目维度
- 题型分布
- 难度分布
- 正确率统计

### 3. 数据持久化

所有批改结果自动保存到数据库：

- **students** 表：学生信息
- **grading_tasks** 表：批改任务
- **grading_results** 表：逐题批改结果
- **grading_statistics** 表：统计数据
- **error_analysis** 表：错误分析

### 4. 流式处理

批改过程实时反馈：

```
📄 解析输入文件...
🔍 分析题目特征...
📋 解析评分标准...
✍️ 批改第 1 题 (1/4)...
✍️ 批改第 2 题 (2/4)...
✍️ 批改第 3 题 (3/4)...
✍️ 批改第 4 题 (4/4)...
📊 聚合结果...
💾 保存数据...
✅ 批改完成！
```

---

## 📦 安装部署

### Railway 部署

1. **创建 PostgreSQL 数据库**

在 Railway 中添加 PostgreSQL 服务，会自动生成 `DATABASE_URL`。

2. **配置环境变量**

```bash
DATABASE_TYPE=postgresql
DATABASE_URL=${{Postgres.DATABASE_URL}}  # Railway 自动注入
LLM_API_KEY=your_api_key_here
LLM_PROVIDER=gemini  # 或 openai
```

3. **部署应用**

```bash
# Railway 会自动检测 requirements.txt 并安装依赖
# 启动命令
streamlit run streamlit_simple.py --server.port=$PORT
```

### 本地部署

```bash
# 1. 克隆仓库
git clone https://github.com/QWERTYjc/aiguru2.0.git
cd aiguru2.0/ai_correction

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
export DATABASE_TYPE=json  # 或 postgresql/mysql
export LLM_API_KEY=your_api_key

# 4. 初始化数据库
python init_database.py

# 5. 启动应用
streamlit run streamlit_simple.py
```

---

## 📖 使用说明

### 1. 准备文件

#### 题目文件 (questions.txt)
```
1. 计算 2 + 3 = ?
A. 4
B. 5
C. 6
D. 7

2. 填空：中国的首都是_____。

3. 简答题：请简述Python的主要特点。
```

#### 答案文件 (001_张三_answers.txt)
```
1. B

2. 北京

3. Python是一种高级编程语言，具有简洁易读的语法。
```

#### 评分标准文件 (marking_scheme.txt)
```
1. 选择题 (2分)
   - 选对得2分

2. 填空题 (2分)
   - 答案正确得2分

3. 简答题 (3分)
   - 提到"高级语言"得1分
   - 提到"语法简洁"得1分
   - 提到"丰富的库"得1分
```

### 2. 上传文件

在 Streamlit 界面中：

1. 选择 **🎓 生产级AI批改** 模式
2. 上传题目文件、答案文件、评分标准（可选）
3. 点击 **🚀 开始批改**

### 3. 查看结果

批改完成后，系统会显示：

- 📊 总体成绩（总分、得分率、等级）
- 📝 逐题详情（每道题的得分和反馈）
- ❌ 错误分析（错误题目、错误类型）
- 📚 知识点掌握情况

### 4. 查看历史

选择 **📚 批改历史** 模式，输入学号查看历史记录。

### 5. 查看班级统计

选择 **📊 班级统计** 模式，输入班级名称查看统计数据。

---

## ⚠️ 注意事项

### 1. 数据库配置

- **生产环境**：强烈推荐使用 PostgreSQL 或 MySQL
- **开发环境**：可以使用 JSON 文件存储
- **Railway 部署**：使用 Railway 提供的 PostgreSQL 服务

### 2. LLM API 配置

系统支持两种 LLM：

- **Gemini**（推荐）：免费额度较高
  ```bash
  export LLM_PROVIDER=gemini
  export GEMINI_API_KEY=your_key
  ```

- **OpenAI**：更强大但需付费
  ```bash
  export LLM_PROVIDER=openai
  export OPENAI_API_KEY=your_key
  ```

- **不配置 LLM**：系统会使用关键词匹配等简单策略

### 3. 文件格式

- 支持格式：`.txt`, `.md`, `.json`, `.csv`
- 文件大小：最大 10MB
- 编码：UTF-8（推荐）或 GBK

### 4. 题目格式

系统支持多种题号格式：

- `1. 题目内容`
- `(1) 题目内容`
- `1) 题目内容`
- `第1题：题目内容`

### 5. 学生信息提取

从文件名提取学生信息：

- `001_张三.txt` → 学号: 001, 姓名: 张三
- `张三_001.txt` → 学号: 001, 姓名: 张三

---

## ❓ 常见问题

### Q1: 数据库连接失败？

**A**: 检查环境变量配置：
```bash
echo $DATABASE_URL
```

确保数据库服务正在运行。

### Q2: LLM API 调用失败？

**A**: 
1. 检查 API 密钥是否正确
2. 检查网络连接
3. 如果不配置 LLM，系统会使用简单策略

### Q3: 题目解析失败？

**A**: 
1. 检查题目格式是否符合要求
2. 确保文件编码为 UTF-8
3. 查看错误日志

### Q4: 如何批量批改？

**A**: 
1. 准备多个答案文件（每个学生一个文件）
2. 文件名格式：`学号_姓名.txt`
3. 一次性上传所有文件

### Q5: 如何导出结果？

**A**: 
1. 批改完成后点击 **📥 下载批改结果**
2. 结果为 Markdown 格式
3. 可以转换为 PDF 或 Word

---

## 📞 技术支持

如有问题，请：

1. 查看 [设计文档](docs/README.md)
2. 运行测试脚本：`python test_production_grading.py`
3. 查看日志文件：`logs/app.log`
4. 提交 Issue 到 GitHub

---

## 📄 许可证

MIT License

---

**祝使用愉快！** 🎉

