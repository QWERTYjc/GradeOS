# 图片保存修复说明

## 问题描述

批改结果中的图片无法保存到 PostgreSQL 数据库的 `grading_page_images` 表中。

## 根本原因

在 `src/graphs/batch_grading.py` 的 `grade_batch` 函数中，构建 `page_results` 时**没有包含图片数据**。

### 问题代码位置

1. **第 2458-2476 行**：学生级批改成功时
2. **第 2511-2530 行**：单页批改失败时  
3. **第 2545-2565 行**：单页批改成功时
4. **第 2606-2617 行**：整个批次失败时

所有这些地方构建的 `page_results` 字典都缺少 `"image"` 字段。

### 导致的后果

在导出节点（`export_results_node`，第 5567 行）尝试保存图片时：

```python
for page_result in page_results:
    image_bytes = page_result.get("image")  # ❌ 永远返回 None
    
    if image_bytes and isinstance(image_bytes, bytes):
        # 永远不会执行到这里
        await save_page_image(...)
```

## 修复方案

在所有构建 `page_results` 的地方添加 `"image"` 字段，将对应的图片数据包含进去。

### 修复内容

#### 1. 学生级批改成功（第 2450-2480 行）

**修改前：**
```python
page_results.append({
    "page_index": page_indices[0] if page_indices else 0,
    "page_indices": page_indices,
    "status": "completed",
    # ... 其他字段
    # ❌ 缺少 image 字段
})
```

**修改后：**
```python
# 为每个页面创建一个结果条目（包含图片数据）
for idx, page_index in enumerate(page_indices):
    image_bytes = images[idx] if idx < len(images) else None
    
    page_results.append({
        "page_index": page_index,
        "page_indices": [page_index],
        "status": "completed",
        # ... 其他字段
        "image": image_bytes,  # ✅ 添加图片数据
    })
```

#### 2. 单页批改失败（第 2511-2530 行）

**添加：**
```python
"image": image,  # ✅ 添加图片数据（即使失败也保存）
```

#### 3. 单页批改成功（第 2545-2565 行）

**添加：**
```python
"image": image,  # ✅ 添加图片数据
```

#### 4. 整个批次失败（第 2606-2617 行）

**修改前：**
```python
for page_idx in page_indices:
    page_results.append({
        "page_index": page_idx,
        # ... 其他字段
        # ❌ 缺少 image 字段
    })
```

**修改后：**
```python
for idx, page_idx in enumerate(page_indices):
    image_bytes = images[idx] if idx < len(images) else None
    page_results.append({
        "page_index": page_idx,
        # ... 其他字段
        "image": image_bytes,  # ✅ 添加图片数据
    })
```

## 验证方法

### 1. 运行测试脚本

```bash
cd GradeOS-Platform/backend
python test_image_save.py
```

### 2. 提交新的批改任务

提交一个新的批改任务，然后检查数据库：

```sql
-- 查看最新的批改历史
SELECT id, batch_id, created_at, total_students 
FROM grading_history 
ORDER BY created_at DESC 
LIMIT 1;

-- 查看该批改历史的图片数量
SELECT 
    grading_history_id,
    COUNT(*) as image_count,
    SUM(LENGTH(image_data)) as total_size_bytes
FROM grading_page_images
WHERE grading_history_id = '<上面查询到的 id>'
GROUP BY grading_history_id;

-- 查看具体的图片记录
SELECT 
    student_key,
    page_index,
    image_format,
    LENGTH(image_data) as size_bytes,
    created_at
FROM grading_page_images
WHERE grading_history_id = '<上面查询到的 id>'
ORDER BY student_key, page_index;
```

### 3. 预期结果

- ✅ `grading_page_images` 表中应该有记录
- ✅ 每个学生的每一页都应该有对应的图片记录
- ✅ `image_data` 字段应该包含有效的图片二进制数据（大小 > 0）
- ✅ 测试脚本应该输出 "🎉 所有图片数据完整！修复成功！"

## 注意事项

1. **图片格式**：默认保存为 PNG 格式
2. **存储大小**：每张图片约 50-200 KB（取决于 DPI 和内容）
3. **性能影响**：图片保存是异步的，不会阻塞批改流程
4. **错误处理**：即使图片保存失败，批改结果仍然会正常保存

## 相关文件

- `src/graphs/batch_grading.py` - 批改流程主文件（已修复）
- `src/db/postgres_grading.py` - 数据库操作（无需修改）
- `scripts/create_image_table.sql` - 图片表结构（无需修改）
- `test_image_save.py` - 验证脚本（新增）

## 修复日期

2026-01-31
