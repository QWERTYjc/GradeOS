# 批注批改功能指南

## 概述

批注批改功能让 AI 在批改时输出带坐标的批注信息，包括：
- **分数标注位置**：在答案旁边标注得分
- **错误圈选区域**：圈出错误的具体位置
- **错误讲解位置**：在错误旁边添加讲解文字
- **正确/部分正确标记**：勾选或三角标记

## 坐标系统

使用**归一化坐标** (0.0-1.0)：
- 坐标原点在图片**左上角**
- x 轴向右增加 (0.0 = 最左, 1.0 = 最右)
- y 轴向下增加 (0.0 = 最上, 1.0 = 最下)

```
(0,0) ────────────────────── (1,0)
  │                            │
  │     图片内容区域            │
  │                            │
(0,1) ────────────────────── (1,1)
```

## API 接口

### 1. 批改单页并返回批注坐标

```http
POST /api/grading/annotate
Content-Type: application/json

{
  "image_base64": "iVBORw0KGgo...",
  "rubrics": [
    {
      "question_id": "1",
      "max_score": 10,
      "question_text": "计算 3 + 5 × 2",
      "standard_answer": "13",
      "scoring_points": [
        {"description": "正确理解运算顺序", "score": 3, "point_id": "1.1"},
        {"description": "正确计算乘法", "score": 3, "point_id": "1.2"},
        {"description": "正确计算加法", "score": 4, "point_id": "1.3"}
      ]
    }
  ],
  "page_index": 0
}
```

**响应示例：**

```json
{
  "success": true,
  "page_annotations": {
    "page_index": 0,
    "annotations": [
      {
        "annotation_type": "score",
        "bounding_box": {"x_min": 0.85, "y_min": 0.15, "x_max": 0.95, "y_max": 0.2},
        "text": "8/10",
        "color": "#FF8800"
      },
      {
        "annotation_type": "error_circle",
        "bounding_box": {"x_min": 0.3, "y_min": 0.25, "x_max": 0.5, "y_max": 0.3},
        "text": "计算错误",
        "color": "#FF0000",
        "question_id": "1",
        "scoring_point_id": "1.3"
      },
      {
        "annotation_type": "comment",
        "bounding_box": {"x_min": 0.55, "y_min": 0.25, "x_max": 0.9, "y_max": 0.32},
        "text": "5×2=10，10+3=13，不是 11",
        "color": "#0066FF"
      },
      {
        "annotation_type": "correct_check",
        "bounding_box": {"x_min": 0.88, "y_min": 0.18, "x_max": 0.92, "y_max": 0.22},
        "color": "#00AA00"
      }
    ],
    "total_score": 8,
    "max_score": 10
  }
}
```

### 2. 渲染批注到图片

```http
POST /api/grading/render
Content-Type: application/json

{
  "image_base64": "iVBORw0KGgo...",
  "annotations": [
    {
      "annotation_type": "score",
      "bounding_box": {"x_min": 0.85, "y_min": 0.15, "x_max": 0.95, "y_max": 0.2},
      "text": "8/10",
      "color": "#FF8800"
    }
  ]
}
```

**响应：** PNG 图片二进制数据

### 3. 一步完成批改并渲染

```http
POST /api/grading/annotate-and-render
Content-Type: application/json

{
  "image_base64": "...",
  "rubrics": [...],
  "page_index": 0
}
```

**响应：** 带批改标记的 PNG 图片

## 批注类型

| 类型 | 说明 | 颜色建议 |
|------|------|----------|
| `score` | 分数标注 | 根据得分率：绿/橙/红 |
| `error_circle` | 错误圈选（椭圆） | 红色 #FF0000 |
| `error_underline` | 错误下划线 | 红色 #FF0000 |
| `correct_check` | 正确勾选 ✓ | 绿色 #00AA00 |
| `partial_check` | 部分正确 △ | 橙色 #FF8800 |
| `wrong_cross` | 错误叉 ✗ | 红色 #FF0000 |
| `comment` | 文字批注 | 蓝色 #0066FF |
| `highlight` | 高亮区域 | 任意颜色（半透明） |

## 前端使用

### TypeScript 类型

```typescript
import type { VisualAnnotation, PageAnnotations } from '@/types/annotation';
```

### 调用 API

```typescript
import { annotatePageWithCoords, renderAnnotationsToImage } from '@/services/annotationApi';

// 批改并获取坐标
const result = await annotatePageWithCoords(imageBase64, rubrics);
if (result.success && result.page_annotations) {
  console.log('批注数量:', result.page_annotations.annotations.length);
}

// 渲染批注到图片
const blob = await renderAnnotationsToImage(imageBase64, annotations);
const url = URL.createObjectURL(blob);
```

### 使用 Canvas 组件渲染

```tsx
import AnnotationCanvas from '@/components/grading/AnnotationCanvas';

<AnnotationCanvas
  imageSrc={imageBase64}
  annotations={pageAnnotations.annotations}
  showText={true}
  onAnnotationClick={(ann) => console.log('点击批注:', ann)}
/>
```

## 坐标转换

将归一化坐标转换为像素坐标：

```typescript
import { toPixelCoords } from '@/types/annotation';

const pixelCoords = toPixelCoords(annotation.bounding_box, imageWidth, imageHeight);
// { x: 850, y: 150, width: 100, height: 50 }
```

## 最佳实践

1. **分数位置**：通常放在答案区域的右上角
2. **错误圈选**：只圈出具体错误的部分，不要圈太大范围
3. **讲解位置**：放在错误旁边或下方，不要遮挡答案
4. **颜色一致性**：保持颜色语义一致（红=错误，绿=正确，橙=部分正确）

## 示例代码

### Python 后端调用

```python
from src.services.annotation_grading import AnnotationGradingService
from src.models.grading_models import QuestionRubric, ScoringPoint

# 创建评分标准
rubrics = [
    QuestionRubric(
        question_id="1",
        max_score=10,
        question_text="计算 3 + 5 × 2",
        standard_answer="13",
        scoring_points=[
            ScoringPoint(description="正确理解运算顺序", score=3, point_id="1.1"),
            ScoringPoint(description="正确计算乘法", score=3, point_id="1.2"),
            ScoringPoint(description="正确计算加法", score=4, point_id="1.3"),
        ]
    )
]

# 批改
service = AnnotationGradingService()
result = await service.grade_page_with_annotations(
    image_data=image_bytes,
    rubrics=rubrics,
    page_index=0
)

# 渲染
from src.services.annotation_renderer import AnnotationRenderer
renderer = AnnotationRenderer()
rendered_image = renderer.render_page(image_bytes, result)
```

### React 前端完整示例

```tsx
'use client';

import { useState } from 'react';
import AnnotationCanvas from '@/components/grading/AnnotationCanvas';
import { annotatePageWithCoords, fileToBase64 } from '@/services/annotationApi';
import type { PageAnnotations, QuestionRubricInput } from '@/types/annotation';

export default function GradingDemo() {
  const [imageBase64, setImageBase64] = useState<string>('');
  const [annotations, setAnnotations] = useState<PageAnnotations | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const base64 = await fileToBase64(file);
    setImageBase64(base64);
  };

  const handleGrade = async () => {
    if (!imageBase64) return;
    
    setLoading(true);
    try {
      const rubrics: QuestionRubricInput[] = [
        {
          question_id: '1',
          max_score: 10,
          question_text: '计算题',
          scoring_points: [
            { description: '解题步骤正确', score: 5 },
            { description: '答案正确', score: 5 },
          ]
        }
      ];

      const result = await annotatePageWithCoords(imageBase64, rubrics);
      if (result.success && result.page_annotations) {
        setAnnotations(result.page_annotations);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4">
      <input type="file" accept="image/*" onChange={handleFileUpload} />
      <button onClick={handleGrade} disabled={!imageBase64 || loading}>
        {loading ? '批改中...' : '开始批改'}
      </button>
      
      {imageBase64 && annotations && (
        <AnnotationCanvas
          imageSrc={imageBase64}
          annotations={annotations.annotations}
          showText={true}
        />
      )}
    </div>
  );
}
```


## 批注集成到批改流程

### 概述

批注功能已集成到主批改流程中。当使用 `grade_student` 方法批改时，AI 会自动输出每道题的批注坐标信息。

### 数据流

```
批改请求 → grade_student() → LLM 输出带批注的 JSON → 解析到 question_details.annotations
```

### 批改结果中的批注字段

批改结果的 `question_details` 中每道题都包含 `annotations` 字段：

```json
{
  "question_details": [
    {
      "question_id": "1",
      "score": 8,
      "max_score": 10,
      "annotations": [
        {
          "type": "score",
          "page_index": 0,
          "bounding_box": {"x_min": 0.85, "y_min": 0.2, "x_max": 0.95, "y_max": 0.25},
          "text": "8/10",
          "color": "#FF8800"
        },
        {
          "type": "error_circle",
          "page_index": 0,
          "bounding_box": {"x_min": 0.3, "y_min": 0.35, "x_max": 0.5, "y_max": 0.38},
          "text": "计算错误",
          "color": "#FF0000"
        }
      ]
    }
  ]
}
```

### 复核后批注修正

当教师复核修改分数后，可以使用以下方法更新批注：

#### 方案 A：增量修正（推荐，低成本）

只更新分数文字，保留其他批注不变：

```python
from src.services.annotation_grading import update_annotations_after_review

# 原始批注
original_annotations = question_result["annotations"]

# 复核后更新
updated_annotations = update_annotations_after_review(
    original_annotations=original_annotations,
    original_score=8.0,
    new_score=7.0,
    max_score=10.0,
    question_id="1"
)
```

#### 方案 B：重新生成（中等成本）

对分数变化较大的题目重新生成批注：

```python
from src.services.annotation_grading import (
    AnnotationGradingService,
    regenerate_annotations_for_question
)

service = AnnotationGradingService()

# 重新生成该题的批注
new_annotations = await regenerate_annotations_for_question(
    service=service,
    image_data=page_image_bytes,
    question_id="1",
    new_score=5.0,
    max_score=10.0,
    feedback="计算过程有多处错误",
    page_index=0
)
```

### 前端渲染批注

从批改结果中提取批注并渲染：

```typescript
// 从批改结果中提取所有批注
const allAnnotations = gradingResult.question_details.flatMap(q => 
  (q.annotations || []).map(ann => ({
    ...ann,
    question_id: q.question_id
  }))
);

// 按页面分组
const annotationsByPage = allAnnotations.reduce((acc, ann) => {
  const pageIndex = ann.page_index || 0;
  if (!acc[pageIndex]) acc[pageIndex] = [];
  acc[pageIndex].push(ann);
  return acc;
}, {} as Record<number, typeof allAnnotations>);

// 渲染每页
{pages.map((pageImage, pageIndex) => (
  <AnnotationCanvas
    key={pageIndex}
    imageSrc={pageImage}
    annotations={annotationsByPage[pageIndex] || []}
    showText={true}
  />
))}
```

### 批注类型颜色规范

| 得分率 | 颜色 | 用途 |
|--------|------|------|
| ≥80% | 绿色 #00AA00 | 优秀 |
| 50%-80% | 橙色 #FF8800 | 部分正确 |
| <50% | 红色 #FF0000 | 需改进 |
| - | 蓝色 #0066FF | 讲解/批注 |

### 环境变量配置

可通过环境变量调整批注行为：

```bash
# 是否在批改时生成批注（默认 true）
GRADING_ENABLE_ANNOTATIONS=true

# 批注最大数量限制（每道题）
GRADING_MAX_ANNOTATIONS_PER_QUESTION=10
```
