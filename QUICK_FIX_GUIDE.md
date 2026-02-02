# 批注功能快速修复指南

## 当前问题诊断

你看到的"Not Found Not Found"错误来自两个地方：
1. `annotationStatus.message` - 生成批注失败
2. `exportStatus.message` - 导出PDF失败

## 根本原因

基于代码分析，问题可能是：

### 1. 数据库表未创建
生产环境的数据库可能没有 `grading_annotations` 表。

**验证方法**：
在Railway后端容器中执行：
```sql
SELECT COUNT(*) FROM grading_annotations;
```

**修复方法**：
批注表会在第一次调用时自动创建（`ensure_annotations_table()`），但如果创建失败，需要手动执行：

```sql
CREATE TABLE IF NOT EXISTS grading_annotations (
    id VARCHAR(64) PRIMARY KEY,
    grading_history_id VARCHAR(64) NOT NULL,
    student_key VARCHAR(128) NOT NULL,
    page_index INTEGER NOT NULL,
    annotation_type VARCHAR(32) NOT NULL,
    bounding_box JSONB NOT NULL,
    text TEXT DEFAULT '',
    color VARCHAR(16) DEFAULT '#FF0000',
    question_id VARCHAR(32) DEFAULT '',
    scoring_point_id VARCHAR(32) DEFAULT '',
    created_by VARCHAR(32) DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_annotations_history ON grading_annotations(grading_history_id);
CREATE INDEX IF NOT EXISTS idx_annotations_student ON grading_annotations(grading_history_id, student_key);
CREATE INDEX IF NOT EXISTS idx_annotations_page ON grading_annotations(grading_history_id, student_key, page_index);
```

### 2. 批注API未正确调用

**问题**：API路由可能没有被正确访问。

**调试步骤**：

1. **打开浏览器开发者工具** (F12)
2. **切换到 Network 标签**
3. **点击"生成批注"按钮**
4. **查看请求详情**：
   - 请求URL应该是：`https://gradeos-production.up.railway.app/api/annotations/generate`
   - 请求方法：POST
   - 状态码：如果是404，说明路由未注册；如果是500，说明后端错误

**如果状态码是404**：
- 检查 Railway 后端日志，确认路由是否注册
- 检查 `src/api/main.py` 是否包含：
  ```python
  from src.api.routes import annotation_grading
  app.include_router(annotation_grading.router, prefix="/api", tags=["批注批改"])
  ```

**如果状态码是500**：
- 查看 Railway 后端日志的详细错误信息
- 可能是数据库连接问题或VLM API密钥问题

### 3. submissionId 或 studentName 缺失

**问题**：前端可能传递了空的 `submissionId` 或 `studentName`。

**验证方法**：
在浏览器Console中输入：
```javascript
console.log('submissionId:', window.location.pathname);
```

**修复方法**：
确保你正在查看一个有效的批改结果，而不是空的或Demo数据。

### 4. 没有图片数据

**问题**：数据库中没有存储学生答题图片。

**验证方法**：
检查 `grading_page_images` 表是否有数据：
```sql
SELECT COUNT(*) FROM grading_page_images 
WHERE grading_history_id = 'your_submission_id';
```

**修复方法**：
- 确保批改时上传了图片
- 检查图片存储服务是否正常

## 立即行动步骤

### 步骤1：检查后端日志
```bash
# 在Railway Dashboard中
# 1. 打开 backend 服务
# 2. 点击 "Logs" 标签
# 3. 搜索 "annotation" 或 "批注"
# 4. 查看是否有错误信息
```

### 步骤2：检查API路由
在浏览器中访问：
```
https://gradeos-production.up.railway.app/api/health
```

应该返回类似：
```json
{
  "status": "healthy",
  "service": "ai-grading-api",
  "version": "1.0.0"
}
```

如果这个都不通，说明后端服务有问题。

### 步骤3：测试批注API
使用浏览器或Postman测试：
```bash
# 测试获取批注
GET https://gradeos-production.up.railway.app/api/annotations/{history_id}/{student_key}

# 应该返回：
{
  "success": true,
  "annotations": [],
  "total": 0
}
```

如果返回404或500，说明API有问题。

### 步骤4：手动创建批注表
如果上述测试失败，在Railway PostgreSQL中手动执行上面的建表SQL。

## 临时解决方案

如果批注功能暂时无法修复，可以：

1. **禁用批注功能**：
   - 隐藏"生成批注"和"导出批注 PDF"按钮
   - 只显示原始图片

2. **使用前端Canvas临时渲染**：
   - 基于批改结果数据在前端Canvas上绘制批注
   - 不依赖后端API

## 联系方式

如果以上步骤都无法解决问题，请提供：

1. **Railway后端日志**（最近50行）
2. **浏览器Network标签截图**（失败的API请求详情）
3. **浏览器Console日志**（错误信息）
4. **数据库查询结果**（表是否存在）

---

**更新时间**：2026-02-02  
**版本**：v1.2.0
