# 批注功能修复总结

## 问题列表
1. ✅ 生成批注和导出PDF显示"Not Found"
2. ⏳ 编辑模式批注位置不准确
3. ⏳ 批注未调用后端AI服务
4. ⏳ 批改标准证据引用未显示

## 已修复问题

### 1. API路径错误 - "Not Found"

**问题原因**：
- 前端 `ResultsView.tsx` 使用 `process.env.NEXT_PUBLIC_API_URL || ''`
- 该环境变量已包含 `/api` (如 `http://localhost:8001/api`)
- 但代码中又拼接了 `/api`，导致路径变成 `/api/api/annotations/...`

**修复方案**：
```typescript
// 修改前
const apiBase = process.env.NEXT_PUBLIC_API_URL || '';
fetch(`${apiBase}/api/annotations/generate`, ...)

// 修改后
const getApiUrl = () => {
    if (typeof window === 'undefined') return 'http://localhost:8001/api';
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:8001/api';
    }
    if (hostname.includes('railway.app')) {
        return 'https://gradeos-production.up.railway.app/api';
    }
    return '/api';
};
const apiBase = getApiUrl();
fetch(`${apiBase}/annotations/generate`, ...) // 去掉多余的 /api
```

**文件修改**：
- `D:\project\GradeOS\GradeOS-Platform\frontend\src\components\console\ResultsView.tsx`
  - 统一API路径获取逻辑
  - 修复所有批注相关API调用

## 待验证问题

### 2. 编辑模式批注位置不准确

**可能原因**：
1. Canvas坐标系与批注坐标系不一致
2. 归一化坐标（0-1）转换问题
3. 图片缩放比例计算错误

**需要检查**：
- `AnnotationEditor.tsx` 坐标转换逻辑
- `AnnotationCanvas.tsx` 渲染坐标计算
- 图片实际尺寸与显示尺寸的比例

**调试建议**：
```typescript
// 在 AnnotationEditor 中添加调试日志
console.log('[坐标调试]', {
    原始坐标: annotation.bounding_box,
    图片尺寸: { width: imageSize.width, height: imageSize.height },
    Canvas尺寸: { width: canvas.width, height: canvas.height },
    转换后坐标: toPixelCoords(annotation.bounding_box, canvas.width, canvas.height)
});
```

### 3. 批注未调用后端AI服务

**状态**：
- 后端服务存在：`annotation_generator.py`
- API路由已注册：`/api/annotations/generate`
- 前端调用逻辑已实现

**需要验证**：
1. 点击"生成批注"按钮
2. 检查浏览器Network标签，确认API调用成功
3. 检查后端日志，确认VLM调用

**预期行为**：
- 前端调用 `POST /api/annotations/generate`
- 后端使用Gemini VLM分析图片
- 生成批注坐标并保存到数据库
- 前端拉取并渲染批注

### 4. 批改标准证据引用未显示

**状态**：
- 前端显示逻辑已存在（第346-351行）
- 数据归一化逻辑正确（gradingResults.ts 142-146行）
- 后端字段支持：`rubric_refs` 或 `rubricRefs`

**需要检查**：
1. 批改结果中是否包含 `rubricRefs` 数据
2. 数据是否为空数组

**调试方法**：
```typescript
// 在 QuestionDetail 组件中添加
console.log('[证据引用调试]', {
    questionId: question.questionId,
    rubricRefs: question.rubricRefs,
    hasRefs: question.rubricRefs && question.rubricRefs.length > 0
});
```

## 后续任务

### 短期任务
1. [ ] 测试批注生成功能（本地 + 生产环境）
2. [ ] 验证PDF导出文件名（应为"批注版_xxx.pdf"）
3. [ ] 检查批注坐标准确性
4. [ ] 确认批改标准引用显示

### 中期优化
1. [ ] 批注透明度可调节
2. [ ] 批注编辑工具增强（撤销/重做）
3. [ ] 批注类型预设模板
4. [ ] 批量生成批注（所有学生）

### 长期规划
1. [ ] 批注历史版本管理
2. [ ] 批注协作编辑（多教师）
3. [ ] 批注模板库
4. [ ] 批注数据分析（常见错误分类）

## 技术栈说明

### 批注渲染
- **前端渲染**：使用 Canvas API（`AnnotationCanvas.tsx`）
- **编辑功能**：使用交互式Canvas（`AnnotationEditor.tsx`）
- **坐标系统**：归一化坐标（0.0-1.0），与图片尺寸无关

### 批注生成
- **VLM模型**：Gemini (后端 `annotation_generator.py`)
- **输入**：答题图片 + 批改结果
- **输出**：批注坐标 + 类型 + 文本 + 颜色

### 批注存储
- **数据库**：PostgreSQL (`grading_annotations` 表)
- **字段**：id, grading_history_id, student_key, page_index, annotation_type, bounding_box, text, color

### 批注类型
- `score`: 分数标注
- `error_circle`: 错误圈选
- `m_mark`: 方法分标注（M1/M0）
- `a_mark`: 答案分标注（A1/A0）
- `comment`: 文字批注
- `step_check`: 步骤正确 ✓
- `step_cross`: 步骤错误 ✗

## 测试清单

### 功能测试
- [ ] 生成批注：点击按钮 → 显示加载态 → 批注出现
- [ ] 导出PDF：点击按钮 → 下载文件 → 文件名正确
- [ ] 编辑批注：拖拽 → 位置改变 → 刷新后保留
- [ ] 添加批注：选择工具 → 点击图片 → 输入文本 → 保存
- [ ] 删除批注：选中 → 点击删除 → 批注消失

### 性能测试
- [ ] 单页批注数量：< 50个
- [ ] 生成批注耗时：< 10秒/页
- [ ] 渲染批注耗时：< 1秒
- [ ] PDF导出耗时：< 5秒

### 兼容性测试
- [ ] Chrome
- [ ] Firefox
- [ ] Safari
- [ ] Edge

## 已知限制

1. **批注密度**：单页批注过多（>50）可能影响性能
2. **图片尺寸**：超大图片（>5MB）可能渲染缓慢
3. **VLM限制**：Gemini API限流（60 RPM）
4. **坐标精度**：批注坐标精度约±2%

## 部署注意事项

### 环境变量
```bash
# 前端 (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8001/api  # 本地开发
# NEXT_PUBLIC_API_URL=https://gradeos-production.up.railway.app/api  # 生产

# 后端 (.env)
GEMINI_API_KEY=your_key_here  # VLM批注生成
DATABASE_URL=postgresql://...  # 批注存储
```

### 数据库迁移
确保 `grading_annotations` 表存在：
```sql
CREATE TABLE IF NOT EXISTS grading_annotations (
    id TEXT PRIMARY KEY,
    grading_history_id TEXT NOT NULL,
    student_key TEXT NOT NULL,
    page_index INTEGER NOT NULL,
    annotation_type TEXT NOT NULL,
    bounding_box JSONB NOT NULL,
    text TEXT DEFAULT '',
    color TEXT DEFAULT '#FF0000',
    question_id TEXT DEFAULT '',
    scoring_point_id TEXT DEFAULT '',
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_annotations_lookup 
    ON grading_annotations(grading_history_id, student_key, page_index);
```

### API路由检查
确认以下路由可访问：
- `GET /api/health` - 健康检查
- `POST /api/annotations/generate` - 生成批注
- `GET /api/annotations/{history_id}/{student_key}` - 获取批注
- `POST /api/annotations` - 创建批注
- `PUT /api/annotations/{id}` - 更新批注
- `DELETE /api/annotations/{id}` - 删除批注
- `POST /api/annotations/export/pdf` - 导出PDF

## 联系与支持

如有问题，请查看：
1. 浏览器控制台（Network标签）
2. 后端日志文件（`batch_grading.log`）
3. Railway部署日志

---
**最后更新**：2026-02-02
**修复版本**：v1.1.0
