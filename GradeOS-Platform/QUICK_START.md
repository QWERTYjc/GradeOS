# GradeOS Platform 快速启动指南

## 🎯 5 分钟快速启动

### 前置条件
- Node.js 18+
- Python 3.11+
- npm 或 yarn

### 步骤 1: 安装依赖

```bash
# 后端依赖
cd GradeOS-Platform/backend
pip install -r requirements.txt

# 前端依赖
cd ../frontend
npm install

# AI 教学助手依赖
cd ../../intellilearn---ai-teaching-agent
npm install
```

### 步骤 2: 启动服务

**方式 A: 使用 PowerShell 脚本 (Windows)**

```powershell
cd GradeOS-Platform
.\start_dev.ps1
```

**方式 B: 手动启动 (所有平台)**

```bash
# 终端 1 - 后端
cd GradeOS-Platform/backend
uvicorn src.api.main:app --reload --port 8001

# 终端 2 - 前端
cd GradeOS-Platform/frontend
npm run dev

# 终端 3 - AI 教学助手
cd intellilearn---ai-teaching-agent
npm run dev
```

### 步骤 3: 访问应用

| 应用 | URL | 用户名 | 密码 |
|------|-----|--------|------|
| GradeOS | http://localhost:3000 | teacher/student | 123456 |
| API 文档 | http://localhost:8001/docs | - | - |
| AI 教学助手 | http://localhost:3000 | - | - |

---

## 🔑 演示账号

### 教师账号
- **用户名**: teacher
- **密码**: 123456
- **功能**: 班级管理、作业发布、AI 批改、数据统计

### 学生账号
- **用户名**: student
- **密码**: 123456
- **功能**: 查看课程、提交作业、错题分析、学情报告

---

## 📱 功能导航

### 教师工作流
1. 登录 → 班级管理 → 创建班级
2. 邀请学生加入班级
3. 发布作业
4. 查看学生提交
5. 使用 AI 批改
6. 查看统计数据

### 学生工作流
1. 登录 → 我的课程 → 加入班级
2. 查看作业列表
3. 提交作业
4. 查看错题分析
5. 查看学情报告

---

## 🐛 故障排除

### 问题: 端口已被占用

```bash
# 查找占用端口的进程
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows

# 杀死进程
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

### 问题: 依赖安装失败

```bash
# 清除缓存并重新安装
npm cache clean --force
npm install

# Python 依赖
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### 问题: 后端无法启动

```bash
# 检查 Python 版本
python --version  # 应该是 3.11+

# 检查虚拟环境
python -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate  # Windows
```

---

## 📚 下一步

- 阅读 [README.md](./README.md) 了解完整功能
- 查看 [docs/VIBE_CODING_GUIDE.md](./docs/VIBE_CODING_GUIDE.md) 了解开发指南
- 查看 [STARTUP_SUMMARY.md](./STARTUP_SUMMARY.md) 了解启动状态

---

## 💡 提示

- 首次启动可能需要 1-2 分钟来编译前端
- 后端会自动重新加载代码更改
- 使用 `http://localhost:8001/docs` 查看完整 API 文档
- 所有演示数据都已预加载，可直接使用

---

**祝你使用愉快！** 🎉
