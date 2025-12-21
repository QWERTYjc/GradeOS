# 本地测试指南 - 前端和后端批改工作流

本指南说明如何在本地快速测试 AI 批改系统的前端显示和后端批改工作流，**无需启动 Docker 或外部服务**。

## 🚀 快速开始 (5 分钟)

### Windows 用户

```powershell
.\quick_start.ps1
```

### macOS/Linux 用户

```bash
bash quick_start.sh
```

## 📋 手动启动步骤

### 步骤 1: 运行后端批改工作流测试

```bash
python test_integration_local.py
```

**预期输出**:
```
✓ 单个试卷批改测试通过
✓ 并发批改测试通过
✓ 前端显示测试通过
✓ 所有工作流组件测试通过
✓ 所有试卷批改完成，共 5 份
✓ 结果已导出到: grading_results.json
✓ 所有测试通过！
```

**生成的文件**:
- `grading_results.json` - 模拟批改结果数据

### 步骤 2: 启动模拟 API 服务器

在新的终端窗口运行:

```bash
python mock_api_server.py
```

**预期输出**:
```
启动模拟 API 服务器...
服务器地址: http://localhost:8001
API 文档: http://localhost:8001/docs
WebSocket: ws://localhost:8001/ws/submissions/{submission_id}
Uvicorn running on http://0.0.0.0:8001
```

**可用端点**:
- `GET /health` - 健康检查
- `GET /api/v1/submissions` - 获取提交列表
- `GET /api/v1/submissions/{id}` - 获取提交详情
- `GET /api/v1/grading-results` - 获取所有批改结果
- `GET /api/v1/grading-results/statistics` - 获取统计信息
- `WebSocket /ws/submissions/{id}` - 实时推送

### 步骤 3: 启动前端开发服务器

在新的终端窗口运行:

```bash
cd frontend
npm install  # 首次运行需要
npm run dev
```

**预期输出**:
```
> frontend@0.1.0 dev
> next dev

  ▲ Next.js 16.0.10
  - Local:        http://localhost:3000
  - Environments: .env.local

✓ Ready in 2.5s
```

## 🌐 访问应用

打开浏览器访问:

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3000 | 批改结果显示 |
| API 文档 | http://localhost:8001/docs | Swagger UI |
| API 地址 | http://localhost:8001 | REST API |

## 📊 测试数据

### 模拟考试信息

- **考试 ID**: exam_2025_01
- **学生数**: 5
- **题目数**: 5
- **满分**: 50

### 学生成绩

| 学生 | 得分 | 满分 | 百分比 | 等级 |
|------|------|------|--------|------|
| 张三 | 41.0 | 50.0 | 82.0% | 良好 |
| 李四 | 41.0 | 50.0 | 82.0% | 良好 |
| 王五 | 41.0 | 50.0 | 82.0% | 良好 |
| 赵六 | 41.0 | 50.0 | 82.0% | 良好 |
| 孙七 | 41.0 | 50.0 | 82.0% | 良好 |

### 统计信息

- 平均分: 41.0
- 最高分: 41.0
- 最低分: 41.0
- 及格率: 100%

## ✅ 前端功能验证

### 结果显示视图

- [ ] 学生排名显示
- [ ] 总分和满分显示
- [ ] 百分比进度条
- [ ] 等级标签 (优秀/良好/及格/不及格)
- [ ] 排名奖章 (前三名)
- [ ] 题目详情展开/收起
- [ ] 题目分数显示
- [ ] 评分点详情显示
- [ ] 评分点说明文本

### 统计信息卡片

- [ ] 总人数: 5
- [ ] 平均分: 41.0
- [ ] 最高分: 41.0
- [ ] 及格率: 100%

### 导出功能

- [ ] CSV 导出按钮可点击
- [ ] 导出文件包含所有学生数据
- [ ] 导出文件格式正确

## ✅ 后端工作流验证

### 单个试卷批改

- [ ] 能够批改单份试卷
- [ ] 正确识别题目数量
- [ ] 正确计算每题分数
- [ ] 正确生成评分点
- [ ] 正确计算总分

### 并发批改

- [ ] 能够并发批改多份试卷
- [ ] 所有试卷都能正确完成
- [ ] 结果聚合正确
- [ ] 没有数据竞争问题

### 结果聚合

- [ ] 正确计算总分
- [ ] 正确计算平均分
- [ ] 正确计算最高分
- [ ] 正确计算及格率

## 🔧 API 测试

### 使用 curl 测试

```bash
# 健康检查
curl http://localhost:8001/health

# 获取提交列表
curl http://localhost:8001/api/v1/submissions

# 获取统计信息
curl http://localhost:8001/api/v1/grading-results/statistics

# 获取单个提交
curl http://localhost:8001/api/v1/submissions/sub_001
```

### 使用 Swagger UI 测试

1. 打开 http://localhost:8001/docs
2. 选择要测试的端点
3. 点击 "Try it out"
4. 点击 "Execute"

## 📁 项目文件结构

```
.
├── test_integration_local.py      # 后端工作流测试脚本
├── mock_api_server.py             # 模拟 API 服务器
├── grading_results.json           # 模拟批改结果数据
├── quick_start.ps1                # Windows 快速启动脚本
├── quick_start.sh                 # macOS/Linux 快速启动脚本
├── TESTING_GUIDE.md               # 详细测试指南
├── TEST_RESULTS_SUMMARY.md        # 测试结果总结
├── LOCAL_TESTING_README.md        # 本文件
└── frontend/
    ├── src/
    │   ├── components/
    │   │   └── console/
    │   │       └── ResultsView.tsx # 前端结果显示组件
    │   └── store/
    │       └── consoleStore.ts     # 前端状态管理
    └── package.json
```

## 🐛 常见问题

### Q: 前端无法连接到 API

**A:** 确保：
1. 模拟 API 服务器正在运行 (`python mock_api_server.py`)
2. API 服务器地址是 http://localhost:8001
3. 前端的 API 配置指向正确的地址

### Q: 模拟数据为空

**A:** 确保：
1. 已运行 `python test_integration_local.py` 生成 `grading_results.json`
2. `grading_results.json` 文件存在于项目根目录
3. 模拟 API 服务器已重新加载数据

### Q: 端口被占用

**A:** 如果端口被占用，可以修改：
- 前端: 在 `frontend` 目录运行 `npm run dev -- -p 3001`
- API: 在 `mock_api_server.py` 中修改 `port=8001` 为其他端口

### Q: Node.js 依赖安装失败

**A:** 尝试：
1. 清除缓存: `npm cache clean --force`
2. 删除 `node_modules` 和 `package-lock.json`
3. 重新安装: `npm install`

## 📈 性能指标

### 后端性能

| 指标 | 值 |
|------|-----|
| 单份试卷批改时间 | ~0.1 秒 |
| 5 份试卷并发批改时间 | ~0.5 秒 |
| 结果导出时间 | <100ms |

### API 性能

| 端点 | 响应时间 |
|------|---------|
| `/health` | <10ms |
| `/api/v1/submissions` | <50ms |
| `/api/v1/grading-results/statistics` | <50ms |

### 前端性能

| 指标 | 值 |
|------|-----|
| 页面加载时间 | <1 秒 |
| 结果渲染时间 | <500ms |
| 题目展开/收起 | <100ms |

## 🔄 工作流

```
试卷图像
  ↓
[文档分割] → 识别题目区域
  ↓
[题目批改] → 为每题生成分数和评分点
  ↓
[结果聚合] → 计算总分和统计信息
  ↓
[结果导出] → 生成 JSON 格式数据
  ↓
[API 提供] → 通过 REST/WebSocket 提供给前端
  ↓
[前端显示] → 渲染结果视图
```

## 📚 相关文档

- [详细测试指南](TESTING_GUIDE.md)
- [测试结果总结](TEST_RESULTS_SUMMARY.md)
- [项目结构](docs/PROJECT_STRUCTURE.md)
- [API 参考](docs/API_REFERENCE.md)

## 🎯 下一步

完成本地测试后，可以：

1. **集成真实 API**: 将前端指向真实的后端 API
2. **启动完整环境**: 运行 `docker-compose up -d` 启动所有服务
3. **运行集成测试**: 执行 `pytest tests/integration/ -v`
4. **性能测试**: 使用 `pytest tests/property/ -v` 运行属性测试

## 💡 提示

- 使用 `Ctrl+C` 停止任何运行的服务
- 在新的终端窗口中运行每个服务
- 确保所有依赖都已安装
- 检查防火墙设置，确保端口可访问

## 📞 支持

如有问题，请：
1. 查看本文件的常见问题部分
2. 查看详细测试指南 (TESTING_GUIDE.md)
3. 查看 API 文档 (http://localhost:8001/docs)
4. 查看浏览器开发者工具 (F12)

---

**祝你测试愉快！** 🎉
