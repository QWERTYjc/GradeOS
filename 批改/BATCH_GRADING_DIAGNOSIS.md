# 批量批改系统诊断报告

## 问题现象

批量批改请求提交成功后，工作流程一直卡在 `running` 状态，没有任何进展：
- 状态始终为 `running`
- `total_students`: 0
- `completed_students`: 0
- `results`: null

## 已完成的修复

### 1. 评分细则解析 ✅
- 实现了子题合并逻辑（7(a), 7(b) → 题目7）
- 支持中文数字转换
- 正确识别19道主题而不是28道子题

### 2. 评分逻辑 ✅
- 改进了评分提示词构建
- 优先使用解析后的评分标准
- 添加了完整的错误处理

### 3. 学生边界检测 ✅
- 改进了题目循环检测逻辑
- 实现了题目编号标准化
- 添加了置信度计算

### 4. API 路由映射 ✅
- 修复了节点到前端的映射
- 所有关键节点正确映射

### 5. API Key 验证 ✅
- API Key 已配置且有效
- 通过直接 API 调用测试成功

## 根本原因分析

通过调试发现，LangGraph 工作流程本身可以正常执行（使用假数据测试成功），但使用真实 PDF 数据时卡住。可能的原因：

### 1. PDF 转图像处理阻塞 ⚠️
```python
# 在 src/api/routes/batch.py 中
rubric_images = await loop.run_in_executor(None, _pdf_to_images, str(rubric_path), 150)
answer_images = await loop.run_in_executor(None, _pdf_to_images, str(answer_path), 150)
```

**问题**：
- 评分标准 PDF：14页，8.4MB
- 学生作答 PDF：49页，2.5MB
- 总共63页需要转换为高分辨率图像（150 DPI）
- 这个过程可能需要几分钟，阻塞了整个请求

**影响**：
- HTTP 请求可能超时
- 图像数据占用大量内存
- 后续 API 调用可能因数据过大而失败

### 2. 图像数据传输问题 ⚠️
```python
payload = {
    "rubric_images": rubric_images,  # 14页高分辨率图像
    "answer_images": answer_images,  # 49页高分辨率图像
    ...
}
```

**问题**：
- 图像数据直接存储在内存中
- 通过 LangGraph 状态传递大量二进制数据
- 可能导致序列化/反序列化问题

### 3. LangGraph 执行卡在第一个节点 ⚠️

从调试日志看，工作流程可能在 `rubric_parse` 节点卡住：
- 该节点需要调用 Gemini API 处理14页评分标准
- 如果图像太大，API 调用可能超时或失败
- 没有看到任何节点执行的日志

## 建议的解决方案

### 方案 1：优化图像处理（短期）

1. **降低图像分辨率**
   ```python
   # 从 150 DPI 降低到 100 DPI
   rubric_images = await loop.run_in_executor(None, _pdf_to_images, str(rubric_path), 100)
   ```

2. **添加图像压缩**
   ```python
   def _pdf_to_images(pdf_path: str, dpi: int = 100, quality: int = 85) -> List[bytes]:
       # ... 转换逻辑 ...
       img.save(img_bytes, format='JPEG', quality=quality, optimize=True)
   ```

3. **添加超时和进度日志**
   ```python
   logger.info(f"开始转换 PDF: {pdf_path}, 预计需要 {page_count * 2} 秒")
   # 转换过程
   logger.info(f"PDF 转换完成: {pdf_path}, 耗时 {elapsed} 秒")
   ```

### 方案 2：使用对象存储（中期）

1. **将图像保存到临时文件**
   ```python
   # 不在内存中传递图像数据
   payload = {
       "rubric_image_paths": [str(path) for path in rubric_image_paths],
       "answer_image_paths": [str(path) for path in answer_image_paths],
   }
   ```

2. **节点按需加载图像**
   ```python
   async def rubric_parse_node(state):
       image_paths = state["rubric_image_paths"]
       images = [load_image(path) for path in image_paths]
       # 处理...
   ```

### 方案 3：分批处理（推荐）

1. **评分标准分批解析**
   - 已在 `RubricParserService` 中实现
   - 每批最多4页

2. **学生作答分批批改**
   - 已在 `grade_batch_node` 中实现
   - 每批10页

3. **添加进度回调**
   ```python
   async def rubric_parse_node(state):
       # 每处理一批，发送进度更新
       await broadcast_progress(batch_id, {
           "type": "rubric_parse_progress",
           "completed_pages": i,
           "total_pages": len(rubric_images)
       })
   ```

## 立即行动项

### 1. 添加详细日志 🔥
在关键节点添加日志，诊断卡住的位置：

```python
# src/api/routes/batch.py - submit_batch 函数
logger.info(f"开始转换评分标准 PDF: {len(rubric_content)} bytes")
rubric_images = await loop.run_in_executor(None, _pdf_to_images, str(rubric_path), 150)
logger.info(f"评分标准转换完成: {len(rubric_images)} 页")

logger.info(f"开始转换学生作答 PDF: {len(answer_content)} bytes")
answer_images = await loop.run_in_executor(None, _pdf_to_images, str(answer_path), 150)
logger.info(f"学生作答转换完成: {len(answer_images)} 页")

logger.info(f"准备启动 LangGraph: payload keys = {list(payload.keys())}")
```

### 2. 降低图像分辨率 🔥
```python
# 从 150 DPI 降低到 72 DPI（屏幕分辨率）
rubric_images = await loop.run_in_executor(None, _pdf_to_images, str(rubric_path), 72)
answer_images = await loop.run_in_executor(None, _pdf_to_images, str(answer_path), 72)
```

### 3. 添加超时保护 🔥
```python
# 为 PDF 转换添加超时
try:
    rubric_images = await asyncio.wait_for(
        loop.run_in_executor(None, _pdf_to_images, str(rubric_path), 72),
        timeout=60.0  # 60秒超时
    )
except asyncio.TimeoutError:
    raise HTTPException(status_code=504, detail="PDF 转换超时")
```

### 4. 测试小数据集 🔥
创建一个只有2-3页的测试 PDF，验证整个流程：

```python
# test_small_batch.py
# 使用前3页进行测试
```

## 下一步

1. **立即实施**：添加详细日志 + 降低分辨率
2. **验证**：重新提交批量批改，观察日志输出
3. **诊断**：确定具体卡住的位置
4. **修复**：根据诊断结果实施针对性修复

## 预期结果

修复后，应该能看到：
- ✅ 评分细则正确解析（19题/105分）
- ✅ 学生边界正确检测（多个学生）
- ✅ 真实评分结果（而非0分）
- ✅ 前端实时更新进度
- ✅ WebSocket 事件正确传输
