# Excel 导出功能依赖修复

## 问题描述

生产环境中 Excel 导出功能报错：
```
ModuleNotFoundError: No module named 'openpyxl'
```

## 原因分析

`src/services/export_service.py` 使用了 `openpyxl` 库，但该依赖未在 `pyproject.toml` 和 `requirements.txt` 中声明。

## 修复内容

### 1. 更新 `pyproject.toml`
在 `dependencies` 列表中添加：
```toml
"openpyxl>=3.1.0",
```

### 2. 重新生成 `requirements.txt`
使用 uv 重新导出依赖：
```bash
cd GradeOS-Platform/backend
uv export --format requirements-txt --no-emit-package ai-grading-agent -o requirements.txt
```

## 部署到 Railway

### 方式一：自动部署（推荐）
1. 提交并推送代码到 Git 仓库
2. Railway 会自动检测到 requirements.txt 的变化并重新部署

### 方式二：手动触发部署
1. 登录 Railway Dashboard
2. 进入 GradeOS Backend 服务
3. 点击 "Deploy" 按钮手动触发重新部署

### 方式三：使用 Railway CLI
```bash
railway up
```

## 验证修复

部署完成后，测试 Excel 导出功能：
1. 访问批改历史页面
2. 点击任意批改记录的导出按钮
3. 选择 "智能 Excel" 选项
4. 确认文件成功下载

## 相关文件

- `GradeOS-Platform/backend/pyproject.toml` - 项目依赖声明
- `GradeOS-Platform/backend/requirements.txt` - 生成的依赖锁定文件
- `GradeOS-Platform/backend/src/services/export_service.py` - Excel 导出服务
- `GradeOS-Platform/backend/src/api/routes/batch_langgraph.py` - 导出 API 端点

## 技术细节

`openpyxl` 是一个用于读写 Excel 2010 xlsx/xlsm/xltx/xltm 文件的 Python 库。
在 `export_service.py` 中用于：
- 创建 Excel 工作簿
- 设置单元格样式（字体、对齐、填充、边框）
- 写入批改结果数据
- 生成格式化的 Excel 报告

## 预防措施

为避免类似问题：
1. 在添加新的 Python 导入时，确保在 `pyproject.toml` 中声明依赖
2. 使用 `uv sync` 或 `uv export` 更新 requirements.txt
3. 在本地测试新功能前运行 `pip install -r requirements.txt` 确保依赖完整
4. 提交代码前检查 `getDiagnostics` 确保没有导入错误
