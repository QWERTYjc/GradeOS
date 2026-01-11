# GradeOS - AI 智能批改系统

<div align="center">

![GradeOS Logo](https://img.shields.io/badge/GradeOS-AI%20Grading-blue?style=for-the-badge&logo=google&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-black?style=flat-square&logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

**基于 Google Gemini 大模型的智能作业批改系统**

[English](#english) | [中文](#中文)

</div>

---

## 中文

### 🌟 项目简介

GradeOS 是一个基于 **Google Gemini 3.0 Flash** 大模型的智能作业批改系统，支持：

- 📄 **PDF/图片识别**：自动识别学生手写作答
- 🎯 **评分标准解析**：AI 自动解析评分细则
- ✍️ **智能批改**：逐题给分并提供详细反馈
- 👥 **多学生批量处理**：一次上传，批量批改
- 🔄 **人工审核**：支持教师审核和修正 AI 批改结果
- 📊 **成绩管理**：班级管理、成绩统计、历史记录

### 🏗️ 系统架构

```
GradeOS-Platform/
├── backend/                 # FastAPI 后端
│   ├── src/
│   │   ├── api/            # REST API & WebSocket
│   │   ├── graphs/         # LangGraph 工作流
│   │   ├── services/       # 业务服务层
│   │   └── orchestration/  # 编排器
│   └── requirements.txt
├── frontend/                # Next.js 16 前端
│   ├── src/
│   │   ├── app/            # App Router 页面
│   │   ├── components/     # React 组件
│   │   └── store/          # Zustand 状态管理
│   └── package.json
└── README.md
```

### 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Next.js 16, React 19, TypeScript, Tailwind CSS, Zustand |
| **后端** | Python 3.12, FastAPI, LangGraph, Pydantic |
| **AI 模型** | Google Gemini 3.0 Flash (Vision) |
| **数据库** | SQLite (默认) / PostgreSQL (可选) |
| **通信** | REST API + WebSocket 实时更新 |

### 🚀 快速开始

#### 1. 环境要求

- Python 3.12+
- Node.js 20+
- Google Gemini API Key

#### 2. 后端安装

```bash
cd GradeOS-Platform/backend

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
echo "GEMINI_API_KEY=your_api_key_here" > .env

# 启动服务
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --reload
```

#### 3. 前端安装

```bash
cd GradeOS-Platform/frontend

# 安装依赖
npm install

# 配置环境变量
echo "NEXT_PUBLIC_API_URL=http://localhost:8001" > .env.local

# 启动开发服务器
npm run dev
```

#### 4. 访问系统

- 前端：http://localhost:3000
- 后端 API：http://localhost:8001
- API 文档：http://localhost:8001/docs

### 📖 使用指南

#### 批改流程

1. **上传文件**：上传评分标准 PDF 和学生作答 PDF/图片
2. **AI 解析**：系统自动解析评分标准，识别学生边界
3. **评分标准确认**：教师审核 AI 解析的评分细则
4. **智能批改**：AI 根据评分标准逐题批改
5. **结果审核**：教师审核批改结果，可修正分数
6. **成绩导出**：将成绩导入班级系统

#### API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/batch/submit` | 提交批改任务 |
| GET | `/api/batch/status/{batch_id}` | 查询批改状态 |
| GET | `/api/batch/rubric/{batch_id}` | 获取解析的评分标准 |
| GET | `/api/batch/results/{batch_id}` | 获取批改结果 |
| WS | `/batch/ws/{batch_id}` | WebSocket 实时进度 |

### 📁 项目结构

```
backend/src/
├── api/
│   ├── main.py              # FastAPI 应用入口
│   └── routes/
│       ├── batch_langgraph.py  # 批改 API
│       ├── unified_api.py      # 统一 API
│       └── class_integration.py # 班级集成
├── graphs/
│   └── batch_grading.py     # LangGraph 批改工作流
├── services/
│   ├── gemini_reasoning.py  # Gemini API 调用
│   ├── rubric_parser.py     # 评分标准解析
│   ├── student_identification.py # 学生识别
│   └── strict_grading.py    # 严格批改逻辑
└── orchestration/
    └── langgraph_orchestrator.py # 工作流编排
```

### 🔧 配置说明

#### 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `GEMINI_API_KEY` | Google Gemini API 密钥 | 必填 |
| `DATABASE_URL` | PostgreSQL 连接串 | 使用 SQLite |
| `OFFLINE_MODE` | 离线模式（跳过 DB） | false |

### 📝 开发说明

#### 工作流节点

LangGraph 批改工作流包含以下节点：

1. `preprocess` - 图像预处理
2. `index` - 学生边界识别
3. `rubric_parse` - 评分标准解析
4. `rubric_review` - 人工审核（中断点）
5. `grading` - AI 批改
6. `results_review` - 结果审核（中断点）
7. `finalize` - 完成并保存

#### 添加新功能

1. 在 `services/` 中添加业务逻辑
2. 在 `graphs/batch_grading.py` 中添加节点
3. 在 `routes/` 中添加 API 端点
4. 前端对应更新组件和状态

### 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## English

### 🌟 Introduction

GradeOS is an intelligent assignment grading system powered by **Google Gemini 3.0 Flash**, featuring:

- 📄 **PDF/Image Recognition**: Automatically recognize handwritten student answers
- 🎯 **Rubric Parsing**: AI automatically parses grading criteria
- ✍️ **Smart Grading**: Score each question with detailed feedback
- 👥 **Batch Processing**: Upload once, grade multiple students
- 🔄 **Human Review**: Support teacher review and correction of AI results
- 📊 **Grade Management**: Class management, statistics, and history

### 🚀 Quick Start

```bash
# Backend
cd GradeOS-Platform/backend
pip install -r requirements.txt
uvicorn src.api.main:app --port 8001 --reload

# Frontend
cd GradeOS-Platform/frontend
npm install && npm run dev
```

### 📞 Contact

- GitHub: [@QWERTYjc](https://github.com/QWERTYjc)
- Project Link: [https://github.com/QWERTYjc/GradeOS](https://github.com/QWERTYjc/GradeOS)

---

<div align="center">

**Made with ❤️ by GradeOS Team**

</div>
