# Design Document

## Overview

本设计文档描述了为 GradeOS 学生 AI 助手添加 function calling 能力的技术方案。通过集成 LLM function calling，AI 助手能够动态调用预定义的工具函数来查询数据库，获取学生的批改结果、知识掌握度、错题记录等数据，从而提供更精准、更个性化的学习辅导。

### 核心目标

1. **动态数据获取**：AI 助手能够根据对话内容自动决定何时需要查询数据库
2. **工具化查询**：将数据库查询封装为标准化的工具函数，支持 LLM 调用
3. **智能响应**：基于查询到的真实数据生成个性化的学习建议
4. **性能优化**：通过异步查询、缓存、并行执行等手段保证响应速度
5. **可扩展性**：易于添加新的工具函数，支持未来功能扩展

### 技术栈

- **LLM Provider**: Google Gemini 2.0 Flash (支持 function calling)
- **Backend**: Python 3.11+, FastAPI
- **Database**: PostgreSQL 15+ (主), SQLite (fallback)
- **Cache**: Redis 7+
- **AI Framework**: LangChain, Pydantic

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Student Frontend                      │
│                    (Next.js + React)                         │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         /assistant/chat Endpoint                     │   │
│  └───────────────────┬──────────────────────────────────┘   │
│                      │                                       │
│                      ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │      Student Assistant Agent                         │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  LLM Client (Gemini 2.0 Flash)                 │  │   │
│  │  │  - Function calling enabled                    │  │   │
│  │  │  - Tool schema registration                    │  │   │
│  │  └────────────────┬───────────────────────────────┘  │   │
│  │                   │                                  │   │
│  │                   ▼                                  │   │
│  │  ┌────────────────────────────────────────────────┐  │   │
│  │  │  Tool Executor                                 │  │   │
│  │  │  - Parse tool calls from LLM                   │  │   │
│  │  │  - Execute tool functions                      │  │   │
│  │  │  - Return results to LLM                       │  │   │
│  │  └────────────────┬───────────────────────────────┘  │   │
│  └───────────────────┼──────────────────────────────────┘   │
│                      │                                       │
│                      ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Tool Functions Registry                      │   │
│  │  - get_grading_history                               │   │
│  │  - get_knowledge_mastery                             │   │
│  │  - get_error_records                                 │   │
│  │  - get_assignment_submissions                        │   │
│  │  - get_class_statistics                              │   │
│  └───────────────────┬──────────────────────────────────┘   │
│                      │                                       │
│                      ▼                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Data Access Layer                            │   │
│  │  ┌────────────────┐  ┌────────────────┐              │   │
│  │  │  PostgreSQL    │  │  Redis Cache   │              │   │
│  │  │  (Primary)     │  │  (Optional)    │              │   │
│  │  └────────────────┘  └────────────────┘              │   │
│  │  ┌────────────────┐                                  │   │
│  │  │  SQLite        │                                  │   │
│  │  │  (Fallback)    │                                  │   │
│  │  └────────────────┘                                  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

1. **学生发送消息** → Frontend 调用 `/assistant/chat` API
2. **Assistant Agent 接收** → 将消息和历史对话传递给 LLM
3. **LLM 分析意图** → 决定是否需要调用工具函数
4. **工具调用** → LLM 返回 function call 请求（工具名 + 参数）
5. **Tool Executor 执行** → 解析请求，调用对应的工具函数
6. **数据库查询** → 工具函数查询 PostgreSQL/SQLite，可能使用 Redis 缓存
7. **返回结果** → 工具函数返回结构化数据
8. **LLM 生成响应** → 将工具返回的数据整合到上下文，生成最终回复
9. **返回前端** → Assistant Agent 返回响应给前端


## Components and Interfaces

### 1. Tool Function Registry

工具函数注册表，管理所有可用的工具函数。

```python
# src/services/assistant_tools.py

from typing import List, Dict, Any, Callable, Optional
from pydantic import BaseModel, Field

class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None

class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter]
    function: Callable  # 实际执行的函数

class ToolRegistry:
    """工具注册表"""
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
    
    def register(self, tool: ToolDefinition) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[ToolDefinition]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def to_gemini_schema(self) -> List[Dict[str, Any]]:
        """转换为 Gemini function calling schema"""
        schemas = []
        for tool in self._tools.values():
            properties = {}
            required = []
            for param in tool.parameters:
                properties[param.name] = {
                    "type": param.type,
                    "description": param.description
                }
                if param.enum:
                    properties[param.name]["enum"] = param.enum
                if param.required:
                    required.append(param.name)
            
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })
        return schemas
```

### 2. Tool Functions

具体的工具函数实现。

```python
# src/services/assistant_tools.py (continued)

async def get_grading_history(
    student_id: str,
    class_id: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    查询学生的批改历史
    
    Args:
        student_id: 学生 ID
        class_id: 班级 ID（可选，用于过滤）
        limit: 返回结果数量限制
    
    Returns:
        {
            "total": int,
            "records": [
                {
                    "assignment_id": str,
                    "assignment_title": str,
                    "score": float,
                    "max_score": float,
                    "percentage": float,
                    "graded_at": str,
                    "feedback_summary": str
                }
            ]
        }
    """
    from src.db.postgres_grading import get_student_results_async
    from src.db import get_homework
    
    try:
        # 查询学生的批改结果
        results = await get_student_results_async(
            student_id=student_id,
            class_id=class_id,
            limit=limit
        )
        
        records = []
        for result in results:
            assignment = get_homework(result.assignment_id) if result.assignment_id else None
            records.append({
                "assignment_id": result.assignment_id or "",
                "assignment_title": assignment.title if assignment else "未知作业",
                "score": float(result.score) if result.score else 0.0,
                "max_score": float(result.max_score) if result.max_score else 0.0,
                "percentage": round((result.score / result.max_score * 100), 1) if result.score and result.max_score else 0.0,
                "graded_at": result.imported_at or "",
                "feedback_summary": result.summary or ""
            })
        
        return {
            "total": len(records),
            "records": records
        }
    except Exception as exc:
        logger.error(f"Failed to get grading history: {exc}")
        return {"total": 0, "records": []}


async def get_knowledge_mastery(
    student_id: str,
    subject: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    查询学生的知识点掌握情况
    
    Args:
        student_id: 学生 ID
        subject: 科目（可选）
        limit: 返回结果数量限制
    
    Returns:
        {
            "total": int,
            "weak_points": [str],  # 薄弱知识点列表
            "mastery": [
                {
                    "concept_id": str,
                    "concept_name": str,
                    "subject": str,
                    "mastery_level": float,  # 0.0 - 1.0
                    "correct_rate": float,  # 0.0 - 1.0
                    "correct_count": int,
                    "total_count": int,
                    "last_evaluated_at": str
                }
            ]
        }
    """
    from src.db import get_connection
    
    try:
        with get_connection() as conn:
            if subject:
                rows = conn.execute(
                    """
                    SELECT skm.*, kp.concept_name, kp.subject
                    FROM student_knowledge_mastery skm
                    JOIN knowledge_points kp ON skm.concept_id = kp.concept_id
                    WHERE skm.student_id = ? AND kp.subject = ?
                    ORDER BY skm.mastery_level ASC, skm.updated_at DESC
                    LIMIT ?
                    """,
                    (student_id, subject, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT skm.*, kp.concept_name, kp.subject
                    FROM student_knowledge_mastery skm
                    JOIN knowledge_points kp ON skm.concept_id = kp.concept_id
                    WHERE skm.student_id = ?
                    ORDER BY skm.mastery_level ASC, skm.updated_at DESC
                    LIMIT ?
                    """,
                    (student_id, limit)
                ).fetchall()
        
        mastery = []
        weak_points = []
        for row in rows:
            mastery_level = float(row["mastery_level"])
            correct_count = int(row["correct_count"])
            total_count = int(row["total_count"])
            correct_rate = correct_count / total_count if total_count > 0 else 0.0
            
            mastery.append({
                "concept_id": row["concept_id"],
                "concept_name": row["concept_name"],
                "subject": row["subject"],
                "mastery_level": mastery_level,
                "correct_rate": correct_rate,
                "correct_count": correct_count,
                "total_count": total_count,
                "last_evaluated_at": row["last_evaluated_at"] or ""
            })
            
            # 掌握度 < 0.6 视为薄弱知识点
            if mastery_level < 0.6:
                weak_points.append(row["concept_name"])
        
        return {
            "total": len(mastery),
            "weak_points": weak_points,
            "mastery": mastery
        }
    except Exception as exc:
        logger.error(f"Failed to get knowledge mastery: {exc}")
        return {"total": 0, "weak_points": [], "mastery": []}


async def get_error_records(
    student_id: str,
    error_type: Optional[str] = None,
    subject: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    查询学生的错题记录
    
    Args:
        student_id: 学生 ID
        error_type: 错误类型（可选）
        subject: 科目（可选）
        limit: 返回结果数量限制
    
    Returns:
        {
            "total": int,
            "records": [
                {
                    "error_id": str,
                    "question_id": str,
                    "subject": str,
                    "question_type": str,
                    "student_answer": str,
                    "correct_answer": str,
                    "error_type": str,
                    "error_severity": str,
                    "root_cause": str,
                    "feedback": str,
                    "created_at": str
                }
            ]
        }
    """
    from src.db import get_connection
    
    try:
        with get_connection() as conn:
            query = "SELECT * FROM error_records WHERE student_id = ?"
            params = [student_id]
            
            if error_type:
                query += " AND error_type = ?"
                params.append(error_type)
            
            if subject:
                query += " AND subject = ?"
                params.append(subject)
            
            query += " ORDER BY error_severity DESC, created_at DESC LIMIT ?"
            params.append(limit)
            
            rows = conn.execute(query, tuple(params)).fetchall()
        
        records = []
        for row in rows:
            detailed_analysis = row["detailed_analysis"]
            if isinstance(detailed_analysis, str):
                try:
                    detailed_analysis = json.loads(detailed_analysis)
                except:
                    detailed_analysis = {}
            
            records.append({
                "error_id": row["error_id"],
                "question_id": row["question_id"] or "",
                "subject": row["subject"] or "",
                "question_type": row["question_type"] or "",
                "student_answer": row["student_answer"] or "",
                "correct_answer": row["correct_answer"] or "",
                "error_type": row["error_type"] or "",
                "error_severity": row["error_severity"] or "",
                "root_cause": row["root_cause"] or "",
                "feedback": detailed_analysis.get("correct_solution", "") if isinstance(detailed_analysis, dict) else "",
                "created_at": row["created_at"] or ""
            })
        
        return {
            "total": len(records),
            "records": records
        }
    except Exception as exc:
        logger.error(f"Failed to get error records: {exc}")
        return {"total": 0, "records": []}


async def get_assignment_submissions(
    student_id: str,
    class_id: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    查询学生的作业提交记录
    
    Args:
        student_id: 学生 ID
        class_id: 班级 ID（可选）
        limit: 返回结果数量限制
    
    Returns:
        {
            "total": int,
            "submissions": [
                {
                    "submission_id": str,
                    "assignment_id": str,
                    "assignment_title": str,
                    "submitted_at": str,
                    "grading_status": str,
                    "score": float,
                    "max_score": float,
                    "percentage": float
                }
            ]
        }
    """
    from src.db import list_student_submissions, get_homework
    
    try:
        submissions_data = list_student_submissions(student_id, limit=limit)
        
        submissions = []
        for sub in submissions_data:
            if class_id and sub.class_id != class_id:
                continue
            
            homework = get_homework(sub.homework_id)
            submissions.append({
                "submission_id": sub.id,
                "assignment_id": sub.homework_id,
                "assignment_title": homework.title if homework else "未知作业",
                "submitted_at": sub.submitted_at or "",
                "grading_status": sub.status or "pending",
                "score": float(sub.score) if sub.score else None,
                "max_score": float(homework.max_score) if homework else None,
                "percentage": round((sub.score / homework.max_score * 100), 1) if sub.score and homework and homework.max_score else None
            })
        
        return {
            "total": len(submissions),
            "submissions": submissions
        }
    except Exception as exc:
        logger.error(f"Failed to get assignment submissions: {exc}")
        return {"total": 0, "submissions": []}


async def get_class_statistics(
    class_id: str,
    assignment_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询班级统计数据
    
    Args:
        class_id: 班级 ID
        assignment_id: 作业 ID（可选，用于查询特定作业的统计）
    
    Returns:
        {
            "class_id": str,
            "class_name": str,
            "assignment_id": str,
            "assignment_title": str,
            "total_students": int,
            "submitted_count": int,
            "average_score": float,
            "max_score": float,
            "min_score": float,
            "pass_rate": float
        }
    """
    from src.db import get_connection, get_class_by_id, get_homework
    
    try:
        class_info = get_class_by_id(class_id)
        if not class_info:
            return {"error": "班级不存在"}
        
        assignment_title = None
        if assignment_id:
            assignment = get_homework(assignment_id)
            assignment_title = assignment.title if assignment else None
        
        with get_connection() as conn:
            if assignment_id:
                rows = conn.execute(
                    """
                    SELECT score, max_score
                    FROM student_grading_results
                    WHERE class_id = ? AND assignment_id = ?
                    AND score IS NOT NULL AND max_score IS NOT NULL
                    """,
                    (class_id, assignment_id)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT score, max_score
                    FROM student_grading_results
                    WHERE class_id = ?
                    AND score IS NOT NULL AND max_score IS NOT NULL
                    """,
                    (class_id,)
                ).fetchall()
        
        if not rows:
            return {
                "class_id": class_id,
                "class_name": class_info.name,
                "assignment_id": assignment_id or "",
                "assignment_title": assignment_title or "",
                "total_students": 0,
                "submitted_count": 0,
                "average_score": 0.0,
                "max_score": 0.0,
                "min_score": 0.0,
                "pass_rate": 0.0
            }
        
        scores = []
        for row in rows:
            if row["max_score"] and row["max_score"] > 0:
                percentage = (row["score"] / row["max_score"]) * 100
                scores.append(percentage)
        
        average_score = sum(scores) / len(scores) if scores else 0.0
        max_score_val = max(scores) if scores else 0.0
        min_score_val = min(scores) if scores else 0.0
        pass_count = sum(1 for s in scores if s >= 60)
        pass_rate = (pass_count / len(scores)) * 100 if scores else 0.0
        
        return {
            "class_id": class_id,
            "class_name": class_info.name,
            "assignment_id": assignment_id or "",
            "assignment_title": assignment_title or "",
            "total_students": len(scores),
            "submitted_count": len(scores),
            "average_score": round(average_score, 1),
            "max_score": round(max_score_val, 1),
            "min_score": round(min_score_val, 1),
            "pass_rate": round(pass_rate, 1)
        }
    except Exception as exc:
        logger.error(f"Failed to get class statistics: {exc}")
        return {"error": str(exc)}


async def get_progress_report(
    student_id: str,
    class_id: Optional[str] = None,
    time_range: str = "month"
) -> Dict[str, Any]:
    """
    生成学生的学习进度报告（与前端 DiagnosisReportResponse 格式匹配）
    
    Args:
        student_id: 学生 ID
        class_id: 班级 ID（可选）
        time_range: 时间范围（week, month, semester）
    
    Returns:
        {
            "student_id": str,
            "report_period": str,  # 例如："2026-01 to 2026-02"
            "overall_assessment": {
                "mastery_score": float,  # 0.0 - 1.0
                "improvement_rate": float,  # 0.0 - 1.0
                "consistency_score": int,  # 0 - 100
                "learning_velocity": float
            },
            "progress_trend": [
                {
                    "date": str,  # "2026-01-15"
                    "score": float,  # 学生分数
                    "average": float  # 班级平均分
                }
            ],
            "knowledge_map": [
                {
                    "knowledge_area": str,  # 知识领域名称
                    "mastery_level": float,  # 0.0 - 1.0
                    "recent_performance": float,
                    "trend": str  # "improving", "stable", "declining"
                }
            ],
            "error_patterns": {
                "total_errors": int,
                "most_common_error_types": [
                    {
                        "type": str,
                        "count": int,
                        "percentage": float
                    }
                ],
                "severity_distribution": {
                    "high": int,
                    "medium": int,
                    "low": int
                }
            },
            "personalized_insights": [str]  # AI 生成的个性化建议
        }
    """
    from src.db import get_connection, list_student_submissions, get_homework
    from datetime import datetime, timedelta
    
    try:
        # 计算时间范围
        now = datetime.utcnow()
        if time_range == "week":
            start_date = now - timedelta(days=7)
            period_label = f"{start_date.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}"
        elif time_range == "semester":
            start_date = now - timedelta(days=120)
            period_label = f"{start_date.strftime('%Y-%m')} to {now.strftime('%Y-%m')}"
        else:  # month
            start_date = now - timedelta(days=30)
            period_label = f"{start_date.strftime('%Y-%m')} to {now.strftime('%Y-%m')}"
        
        # 查询作业提交记录
        submissions = list_student_submissions(student_id, limit=50)
        
        # 过滤时间范围内的提交
        recent_submissions = []
        for sub in submissions:
            try:
                sub_date = datetime.fromisoformat(sub.submitted_at.replace('Z', '+00:00'))
                if sub_date >= start_date:
                    recent_submissions.append(sub)
            except:
                continue
        
        # 计算整体评估
        scores = [sub.score for sub in recent_submissions if sub.score is not None]
        average_score = sum(scores) / len(scores) if scores else 0.0
        mastery_score = average_score / 100.0 if average_score > 0 else 0.0
        
        # 计算提升率（与上一时期对比）
        # TODO: 需要历史数据，暂时使用模拟值
        improvement_rate = 0.05  # 5% 提升
        
        # 计算一致性分数（分数波动越小，一致性越高）
        if len(scores) > 1:
            score_variance = sum((s - average_score) ** 2 for s in scores) / len(scores)
            consistency_score = max(0, 100 - int(score_variance / 10))
        else:
            consistency_score = 100
        
        # 生成进度趋势数据
        progress_trend = []
        for sub in sorted(recent_submissions, key=lambda x: x.submitted_at or ""):
            if sub.score is not None:
                # 查询班级平均分（如果有班级数据）
                class_average = 75.0  # 默认值
                if class_id:
                    with get_connection() as conn:
                        avg_row = conn.execute(
                            """
                            SELECT AVG(score * 100.0 / max_score) as avg_percentage
                            FROM student_grading_results
                            WHERE class_id = ? AND score IS NOT NULL AND max_score > 0
                            """,
                            (class_id,)
                        ).fetchone()
                        if avg_row and avg_row["avg_percentage"]:
                            class_average = float(avg_row["avg_percentage"])
                
                progress_trend.append({
                    "date": sub.submitted_at[:10] if sub.submitted_at else "",
                    "score": float(sub.score),
                    "average": class_average
                })
        
        # 查询知识点掌握情况
        with get_connection() as conn:
            knowledge_rows = conn.execute(
                """
                SELECT skm.*, kp.concept_name, kp.subject
                FROM student_knowledge_mastery skm
                JOIN knowledge_points kp ON skm.concept_id = kp.concept_id
                WHERE skm.student_id = ?
                ORDER BY skm.updated_at DESC
                LIMIT 10
                """,
                (student_id,)
            ).fetchall()
        
        knowledge_map = []
        for row in knowledge_rows:
            mastery_level = float(row["mastery_level"])
            knowledge_map.append({
                "knowledge_area": row["subject"] or row["concept_name"],
                "mastery_level": mastery_level,
                "recent_performance": mastery_level,  # TODO: 计算最近表现
                "trend": "stable"  # TODO: 计算趋势
            })
        
        # 查询错题模式
        with get_connection() as conn:
            error_rows = conn.execute(
                """
                SELECT error_type, error_severity, COUNT(*) as count
                FROM error_records
                WHERE student_id = ?
                GROUP BY error_type, error_severity
                ORDER BY count DESC
                """,
                (student_id,)
            ).fetchall()
        
        total_errors = sum(row["count"] for row in error_rows)
        error_type_counts = {}
        severity_distribution = {"high": 0, "medium": 0, "low": 0}
        
        for row in error_rows:
            error_type = row["error_type"] or "Unknown"
            count = int(row["count"])
            error_type_counts[error_type] = error_type_counts.get(error_type, 0) + count
            
            severity = row["error_severity"]
            if severity in severity_distribution:
                severity_distribution[severity] += count
        
        most_common_error_types = [
            {
                "type": error_type,
                "count": count,
                "percentage": round((count / total_errors * 100), 1) if total_errors > 0 else 0.0
            }
            for error_type, count in sorted(error_type_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        # 生成个性化建议
        personalized_insights = []
        
        if mastery_score >= 0.9:
            personalized_insights.append("🎉 Outstanding performance! You're mastering the material exceptionally well.")
        elif mastery_score >= 0.7:
            personalized_insights.append("👍 Good progress! Keep up the consistent effort to reach mastery level.")
        else:
            personalized_insights.append("💪 Focus on strengthening your foundation. Review core concepts regularly.")
        
        if consistency_score < 70:
            personalized_insights.append("📊 Your scores show some variation. Try to maintain a steady study routine for better consistency.")
        
        if len(knowledge_map) > 0:
            weak_areas = [k for k in knowledge_map if k["mastery_level"] < 0.6]
            if weak_areas:
                weak_names = ", ".join([k["knowledge_area"] for k in weak_areas[:2]])
                personalized_insights.append(f"🎯 Priority areas for improvement: {weak_names}. Allocate extra practice time here.")
        
        if total_errors > 0 and most_common_error_types:
            top_error = most_common_error_types[0]["type"]
            personalized_insights.append(f"⚠️ Watch out for {top_error} errors. Review related concepts and practice similar problems.")
        
        if len(progress_trend) >= 3:
            recent_scores = [pt["score"] for pt in progress_trend[-3:]]
            if all(recent_scores[i] >= recent_scores[i-1] for i in range(1, len(recent_scores))):
                personalized_insights.append("📈 Great momentum! Your recent scores show consistent improvement.")
        
        return {
            "student_id": student_id,
            "report_period": period_label,
            "overall_assessment": {
                "mastery_score": mastery_score,
                "improvement_rate": improvement_rate,
                "consistency_score": consistency_score,
                "learning_velocity": 0.8  # TODO: 计算学习速度
            },
            "progress_trend": progress_trend,
            "knowledge_map": knowledge_map,
            "error_patterns": {
                "total_errors": total_errors,
                "most_common_error_types": most_common_error_types,
                "severity_distribution": severity_distribution
            },
            "personalized_insights": personalized_insights
        }
    except Exception as exc:
        logger.error(f"Failed to get progress report: {exc}")
        return {
            "student_id": student_id,
            "report_period": "N/A",
            "overall_assessment": {
                "mastery_score": 0.0,
                "improvement_rate": 0.0,
                "consistency_score": 0,
                "learning_velocity": 0.0
            },
            "progress_trend": [],
            "knowledge_map": [],
            "error_patterns": {
                "total_errors": 0,
                "most_common_error_types": [],
                "severity_distribution": {"high": 0, "medium": 0, "low": 0}
            },
            "personalized_insights": ["Unable to generate report. Please try again later."]
        }
```


### 3. Tool Executor

工具执行器，负责解析 LLM 的 function call 请求并执行对应的工具函数。

```python
# src/services/tool_executor.py

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ToolCall(BaseModel):
    """工具调用请求"""
    id: str  # 调用 ID
    name: str  # 工具名称
    arguments: Dict[str, Any]  # 参数

class ToolResult(BaseModel):
    """工具调用结果"""
    call_id: str
    name: str
    result: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: int = 0

class ToolExecutor:
    """工具执行器"""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.timeout_seconds = 5.0
    
    async def execute(
        self,
        tool_calls: List[ToolCall],
        student_id: str,
        parallel: bool = True
    ) -> List[ToolResult]:
        """
        执行工具调用
        
        Args:
            tool_calls: 工具调用列表
            student_id: 学生 ID（用于权限验证）
            parallel: 是否并行执行
        
        Returns:
            工具调用结果列表
        """
        if parallel:
            tasks = [
                self._execute_single(call, student_id)
                for call in tool_calls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r if not isinstance(r, Exception) else self._error_result(call, str(r)) 
                    for r, call in zip(results, tool_calls)]
        else:
            results = []
            for call in tool_calls:
                result = await self._execute_single(call, student_id)
                results.append(result)
            return results
    
    async def _execute_single(
        self,
        call: ToolCall,
        student_id: str
    ) -> ToolResult:
        """执行单个工具调用"""
        start_time = time.time()
        
        try:
            # 获取工具定义
            tool = self.registry.get_tool(call.name)
            if not tool:
                return ToolResult(
                    call_id=call.id,
                    name=call.name,
                    result={},
                    error=f"Tool '{call.name}' not found",
                    execution_time_ms=0
                )
            
            # 权限验证：确保学生只能查询自己的数据
            if "student_id" in call.arguments:
                if call.arguments["student_id"] != student_id:
                    return ToolResult(
                        call_id=call.id,
                        name=call.name,
                        result={},
                        error="Permission denied: cannot query other student's data",
                        execution_time_ms=0
                    )
            else:
                # 自动注入 student_id
                call.arguments["student_id"] = student_id
            
            # 执行工具函数（带超时）
            result = await asyncio.wait_for(
                tool.function(**call.arguments),
                timeout=self.timeout_seconds
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # 记录日志
            logger.info(
                f"Tool executed: {call.name}, "
                f"student_id={student_id}, "
                f"args={call.arguments}, "
                f"time={execution_time}ms"
            )
            
            return ToolResult(
                call_id=call.id,
                name=call.name,
                result=result,
                error=None,
                execution_time_ms=execution_time
            )
        
        except asyncio.TimeoutError:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"Tool timeout: {call.name}, time={execution_time}ms")
            return ToolResult(
                call_id=call.id,
                name=call.name,
                result={},
                error=f"Tool execution timeout after {self.timeout_seconds}s",
                execution_time_ms=execution_time
            )
        
        except Exception as exc:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"Tool execution failed: {call.name}, error={exc}", exc_info=True)
            return ToolResult(
                call_id=call.id,
                name=call.name,
                result={},
                error=str(exc),
                execution_time_ms=execution_time
            )
    
    def _error_result(self, call: ToolCall, error: str) -> ToolResult:
        """创建错误结果"""
        return ToolResult(
            call_id=call.id,
            name=call.name,
            result={},
            error=error,
            execution_time_ms=0
        )
```

### 4. LLM Client with Function Calling

扩展现有的 LLM Client 以支持 function calling。

```python
# src/services/llm_client.py (扩展)

from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class FunctionCallRequest(BaseModel):
    """Function call 请求"""
    name: str
    arguments: Dict[str, Any]

class LLMResponse(BaseModel):
    """LLM 响应"""
    content: str
    function_calls: Optional[List[FunctionCallRequest]] = None
    finish_reason: str  # "stop", "function_call", "length", "error"
    model: str
    usage: Dict[str, Any]

class LLMClient:
    """LLM 客户端（支持 function calling）"""
    
    async def invoke_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[Dict[str, Any]],  # Gemini tool schema
        purpose: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """
        调用 LLM（支持 function calling）
        
        Args:
            messages: 消息列表
            tools: 工具定义列表（Gemini schema 格式）
            purpose: 调用目的
            temperature: 温度参数
            max_tokens: 最大 token 数
        
        Returns:
            LLM 响应（可能包含 function calls）
        """
        # 实现 Gemini function calling 调用逻辑
        # 参考 Gemini API 文档
        pass
```

### 5. Student Assistant Agent (Updated)

更新学生助手 Agent 以支持 function calling。

现有的 `/v1/diagnosis/report/{student_id}` API 也应该使用 function calling 来获取数据，而不是直接查询数据库。

```python
# src/api/routes/unified_api.py (更新)

@router.get(
    "/v1/diagnosis/report/{student_id}",
    response_model=DiagnosisReportResponse,
    tags=["Error Analysis"],
)
async def get_diagnosis_report(student_id: str, class_id: Optional[str] = None):
    """
    Generate a diagnosis report for a student.
    
    现在使用 function calling 来获取数据，确保数据一致性。
    """
    # 使用 get_progress_report 工具函数获取数据
    report_data = await get_progress_report(
        student_id=student_id,
        class_id=class_id,
        time_range="month"
    )
    
    # 直接返回，数据格式已经匹配 DiagnosisReportResponse
    return DiagnosisReportResponse(**report_data)
```

**优势：**
1. **数据一致性**：AI 助手和 diagnosis report API 使用相同的数据源
2. **代码复用**：避免重复的数据查询逻辑
3. **易于维护**：只需要维护一套工具函数
4. **统一优化**：缓存、性能优化在工具函数层统一处理



更新学生助手 Agent 以支持 function calling。

```python
# src/services/student_assistant_agent.py (更新)

from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from src.services.assistant_tools import ToolRegistry, get_grading_history, get_knowledge_mastery, get_error_records, get_assignment_submissions, get_class_statistics
from src.services.tool_executor import ToolExecutor, ToolCall
from src.services.llm_client import get_llm_client

class StudentAssistantAgent:
    """学生助手 Agent（支持 function calling）"""
    
    def __init__(self):
        self.llm_client = get_llm_client()
        self.registry = self._init_registry()
        self.executor = ToolExecutor(self.registry)
    
    def _init_registry(self) -> ToolRegistry:
        """初始化工具注册表"""
        registry = ToolRegistry()
        
        # 注册工具
        registry.register(ToolDefinition(
            name="get_grading_history",
            description="查询学生的批改历史和成绩记录。当学生询问自己的成绩、分数、批改结果时使用。",
            parameters=[
                ToolParameter(name="student_id", type="string", description="学生 ID", required=True),
                ToolParameter(name="class_id", type="string", description="班级 ID（可选，用于过滤特定班级的成绩）", required=False),
                ToolParameter(name="limit", type="integer", description="返回结果数量限制，默认 10", required=False)
            ],
            function=get_grading_history
        ))
        
        registry.register(ToolDefinition(
            name="get_knowledge_mastery",
            description="查询学生的知识点掌握情况。当学生询问自己的薄弱知识点、掌握情况时使用。",
            parameters=[
                ToolParameter(name="student_id", type="string", description="学生 ID", required=True),
                ToolParameter(name="subject", type="string", description="科目（可选）", required=False),
                ToolParameter(name="limit", type="integer", description="返回结果数量限制，默认 20", required=False)
            ],
            function=get_knowledge_mastery
        ))
        
        registry.register(ToolDefinition(
            name="get_error_records",
            description="查询学生的错题记录。当学生询问错题、做错的题目时使用。",
            parameters=[
                ToolParameter(name="student_id", type="string", description="学生 ID", required=True),
                ToolParameter(name="error_type", type="string", description="错误类型（可选）", required=False),
                ToolParameter(name="subject", type="string", description="科目（可选）", required=False),
                ToolParameter(name="limit", type="integer", description="返回结果数量限制，默认 10", required=False)
            ],
            function=get_error_records
        ))
        
        registry.register(ToolDefinition(
            name="get_assignment_submissions",
            description="查询学生的作业提交记录。当学生询问作业完成情况、提交记录时使用。",
            parameters=[
                ToolParameter(name="student_id", type="string", description="学生 ID", required=True),
                ToolParameter(name="class_id", type="string", description="班级 ID（可选）", required=False),
                ToolParameter(name="limit", type="integer", description="返回结果数量限制，默认 10", required=False)
            ],
            function=get_assignment_submissions
        ))
        
        registry.register(ToolDefinition(
            name="get_class_statistics",
            description="查询班级统计数据。当学生询问班级平均分、排名、班级表现时使用。",
            parameters=[
                ToolParameter(name="class_id", type="string", description="班级 ID", required=True),
                ToolParameter(name="assignment_id", type="string", description="作业 ID（可选，用于查询特定作业的统计）", required=False)
            ],
            function=get_class_statistics
        ))
        
        registry.register(ToolDefinition(
            name="get_progress_report",
            description="生成学生的学习进度报告。当学生询问学习进度、成长趋势、整体表现时使用。",
            parameters=[
                ToolParameter(name="student_id", type="string", description="学生 ID", required=True),
                ToolParameter(name="class_id", type="string", description="班级 ID（可选）", required=False),
                ToolParameter(name="time_range", type="string", description="时间范围：week, month, semester", required=False, enum=["week", "month", "semester"])
            ],
            function=get_progress_report
        ))
        
        return registry
    
    async def ainvoke(
        self,
        message: str,
        student_context: Dict[str, Any],
        session_mode: str = "learning",
        concept_topic: str = "general",
        history: List[BaseMessage] = None
    ) -> AssistantResponse:
        """
        调用助手（支持 function calling）
        
        Args:
            message: 学生消息
            student_context: 学生上下文
            session_mode: 会话模式
            concept_topic: 概念主题
            history: 历史消息
        
        Returns:
            助手响应
        """
        student_id = student_context.get("student_id")
        if not student_id:
            raise ValueError("student_id is required")
        
        # 构建系统提示
        system_prompt = self._build_system_prompt(student_context, session_mode)
        
        # 构建消息列表
        messages = [SystemMessage(content=system_prompt)]
        if history:
            messages.extend(history)
        messages.append(HumanMessage(content=message))
        
        # 获取工具 schema
        tool_schemas = self.registry.to_gemini_schema()
        
        # 第一次调用 LLM（可能返回 function calls）
        response = await self.llm_client.invoke_with_tools(
            messages=messages,
            tools=tool_schemas,
            purpose="assistant_chat",
            temperature=0.7
        )
        
        # 如果 LLM 请求调用工具
        if response.function_calls:
            # 执行工具调用
            tool_calls = [
                ToolCall(
                    id=f"call_{i}",
                    name=fc.name,
                    arguments=fc.arguments
                )
                for i, fc in enumerate(response.function_calls)
            ]
            
            tool_results = await self.executor.execute(
                tool_calls=tool_calls,
                student_id=student_id,
                parallel=True
            )
            
            # 将工具结果添加到消息中
            for result in tool_results:
                if result.error:
                    messages.append(SystemMessage(
                        content=f"Tool '{result.name}' failed: {result.error}"
                    ))
                else:
                    messages.append(SystemMessage(
                        content=f"Tool '{result.name}' result: {json.dumps(result.result, ensure_ascii=False)}"
                    ))
            
            # 第二次调用 LLM（基于工具结果生成最终响应）
            final_response = await self.llm_client.invoke_with_tools(
                messages=messages,
                tools=tool_schemas,
                purpose="assistant_chat",
                temperature=0.7
            )
            
            return AssistantResponse(
                content=final_response.content,
                model=final_response.model,
                usage=final_response.usage,
                tool_calls_made=len(tool_results)
            )
        
        # 如果不需要调用工具，直接返回响应
        return AssistantResponse(
            content=response.content,
            model=response.model,
            usage=response.usage,
            tool_calls_made=0
        )
    
    def _build_system_prompt(
        self,
        student_context: Dict[str, Any],
        session_mode: str
    ) -> str:
        """构建系统提示"""
        prompt = f"""你是 GradeOS 学生学习助手，帮助学生提高学习效果。

**你的能力：**
1. 查询学生的批改历史和成绩（使用 get_grading_history 工具）
2. 分析学生的知识点掌握情况（使用 get_knowledge_mastery 工具）
3. 查看学生的错题记录（使用 get_error_records 工具）
4. 查询学生的作业提交情况（使用 get_assignment_submissions 工具）
5. 查看班级统计数据（使用 get_class_statistics 工具）

**使用工具的时机：**
- 当学生询问"我的成绩怎么样"、"我最近的分数"时，使用 get_grading_history
- 当学生询问"我哪些知识点薄弱"、"我掌握得怎么样"时，使用 get_knowledge_mastery
- 当学生询问"我的错题"、"我做错了哪些题"时，使用 get_error_records
- 当学生询问"我交了哪些作业"、"作业完成情况"时，使用 get_assignment_submissions
- 当学生询问"班级平均分"、"我在班里排第几"时，使用 get_class_statistics
- 当学生询问"我的学习进度"、"我的成长趋势"、"整体表现"时，使用 get_progress_report

**重要原则：**
1. 优先使用工具查询真实数据，而不是基于假设回答
2. 如果工具返回空数据，友好地告知学生暂无相关数据
3. 基于查询到的数据提供个性化、具体的学习建议
4. 使用苏格拉底式提问引导学生思考
5. 保持鼓励和支持的语气

**学生信息：**
- 学生 ID: {student_context.get('student_id')}
- 班级: {', '.join(student_context.get('class_names', {}).values())}

**会话模式：** {session_mode}
"""
        return prompt


### 6. Integration with Existing Diagnosis Report API

现有的 `/v1/diagnosis/report/{student_id}` API 也应该使用 function calling 来获取数据，而不是直接查询数据库。

```python
# src/api/routes/unified_api.py (更新)

@router.get(
    "/v1/diagnosis/report/{student_id}",
    response_model=DiagnosisReportResponse,
    tags=["Error Analysis"],
)
async def get_diagnosis_report(student_id: str, class_id: Optional[str] = None):
    """
    Generate a diagnosis report for a student.
    
    现在使用 function calling 来获取数据，确保数据一致性。
    """
    # 使用 get_progress_report 工具函数获取数据
    report_data = await get_progress_report(
        student_id=student_id,
        class_id=class_id,
        time_range="month"
    )
    
    # 直接返回，数据格式已经匹配 DiagnosisReportResponse
    return DiagnosisReportResponse(**report_data)
```

**优势：**
1. **数据一致性**：AI 助手和 diagnosis report API 使用相同的数据源
2. **代码复用**：避免重复的数据查询逻辑
3. **易于维护**：只需要维护一套工具函数
4. **统一优化**：缓存、性能优化在工具函数层统一处理

```


## Data Models

### Tool-Related Models

```python
# src/models/assistant_models.py (扩展)

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class GradingHistoryRecord(BaseModel):
    """批改历史记录"""
    assignment_id: str
    assignment_title: str
    score: float
    max_score: float
    percentage: float
    graded_at: str
    feedback_summary: str

class KnowledgeMasteryRecord(BaseModel):
    """知识掌握记录"""
    concept_id: str
    concept_name: str
    subject: str
    mastery_level: float  # 0.0 - 1.0
    correct_rate: float  # 0.0 - 1.0
    correct_count: int
    total_count: int
    last_evaluated_at: str

class ErrorRecord(BaseModel):
    """错题记录"""
    error_id: str
    question_id: str
    subject: str
    question_type: str
    student_answer: str
    correct_answer: str
    error_type: str
    error_severity: str  # "high", "medium", "low"
    root_cause: str
    feedback: str
    created_at: str

class AssignmentSubmissionRecord(BaseModel):
    """作业提交记录"""
    submission_id: str
    assignment_id: str
    assignment_title: str
    submitted_at: str
    grading_status: str  # "pending", "processing", "completed"
    score: Optional[float] = None
    max_score: Optional[float] = None
    percentage: Optional[float] = None

class ClassStatistics(BaseModel):
    """班级统计"""
    class_id: str
    class_name: str
    assignment_id: str
    assignment_title: str
    total_students: int
    submitted_count: int
    average_score: float
    max_score: float
    min_score: float
    pass_rate: float

class ToolCallLog(BaseModel):
    """工具调用日志"""
    log_id: str
    student_id: str
    tool_name: str
    arguments: Dict[str, Any]
    result_summary: str  # 结果摘要（不包含完整数据）
    execution_time_ms: int
    success: bool
    error_message: Optional[str] = None
    created_at: str
```

### Database Schema Updates

需要添加工具调用日志表：

```sql
-- 工具调用日志表
CREATE TABLE IF NOT EXISTS tool_call_logs (
    log_id VARCHAR(100) PRIMARY KEY,
    student_id VARCHAR(50) REFERENCES users(user_id),
    tool_name VARCHAR(100) NOT NULL,
    arguments JSONB DEFAULT '{}',
    result_summary TEXT,
    execution_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_logs_student ON tool_call_logs(student_id);
CREATE INDEX IF NOT EXISTS idx_tool_logs_created ON tool_call_logs(created_at);
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. 
Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

在定义具体属性之前，我们需要识别并消除冗余：

**识别的冗余：**
1. 多个"工具选择"属性（1.1, 2.1, 3.1, 4.1, 5.1）可以合并为一个通用属性
2. 多个"返回数据结构"属性（1.2, 2.2, 3.2, 4.2, 5.2）可以合并
3. 多个"过滤功能"属性（2.4, 3.4, 4.4, 5.5）可以合并
4. 多个"空数据提示"属性（2.5, 4.5, 5.4）可以合并为边界情况示例

**合并后的核心属性：**
- 工具选择正确性（合并 1.1, 2.1, 3.1, 4.1, 5.1）
- 返回数据完整性（合并 1.2, 2.2, 3.2, 4.2, 5.2）
- 过滤功能正确性（合并 2.4, 3.4, 4.4, 5.5）
- 排序逻辑正确性（1.3, 3.3）
- 权限控制（7.4）
- 错误处理（1.4, 6.4）
- 参数生成正确性（6.2）
- 数据整合（6.3）
- 多工具调用（6.5）
- 异步执行（10.1）
- 缓存机制（7.5, 10.2）
- 分页限制（10.3）
- 并行执行（10.4）
- 超时处理（10.5）
- 日志记录（9.1, 9.2, 9.3, 9.4, 9.5）

### Properties

Property 1: 工具选择正确性
*For any* 学生查询消息，如果消息包含特定关键词（如"成绩"、"分数"、"批改结果"），LLM 应该选择调用对应的工具（如 get_grading_history）
**Validates: Requirements 1.1, 2.1, 3.1, 4.1, 5.1**

Property 2: 返回数据完整性
*For any* 工具调用，返回的 JSON 数据应该包含所有必需字段，且字段类型正确
**Validates: Requirements 1.2, 2.2, 3.2, 4.2, 5.2**

Property 3: 排序逻辑正确性
*For any* 返回多条记录的工具调用，结果应该按指定规则排序（如时间倒序、严重程度降序）
**Validates: Requirements 1.3, 3.3**

Property 4: 过滤功能正确性
*For any* 带过滤参数的工具调用，返回结果应该只包含符合过滤条件的记录
**Validates: Requirements 2.4, 3.4, 4.4, 5.5**

Property 5: 权限控制
*For any* 工具调用，如果学生 A 尝试查询学生 B 的数据，系统应该拒绝并返回权限错误
**Validates: Requirements 7.4**

Property 6: 错误处理
*For any* 工具调用，如果数据库查询失败，系统应该返回空结果或错误信息，而不是崩溃
**Validates: Requirements 1.4, 6.4**

Property 7: 参数生成正确性
*For any* LLM 生成的 function call，参数应该符合工具的 JSON Schema 定义
**Validates: Requirements 6.2, 7.1**

Property 8: 数据整合
*For any* 工具调用完成后，工具返回的数据应该被正确添加到 LLM 的上下文消息中
**Validates: Requirements 6.3**

Property 9: 多工具调用
*For any* 需要多个工具的查询，系统应该支持连续调用多个工具
**Validates: Requirements 6.5**

Property 10: 异步执行
*For any* 工具调用，查询函数应该是异步的（返回 awaitable 对象）
**Validates: Requirements 10.1**

Property 11: 缓存机制
*For any* 相同的工具调用（相同参数），第二次调用应该使用缓存结果
**Validates: Requirements 7.5, 10.2**

Property 12: 分页限制
*For any* 工具调用，返回结果数量不应超过指定的 limit 参数
**Validates: Requirements 10.3**

Property 13: 并行执行
*For any* 多个独立的工具调用，系统应该支持并行执行以提高性能
**Validates: Requirements 10.4**

Property 14: 超时处理
*For any* 工具调用，如果执行时间超过 5 秒，系统应该返回超时错误
**Validates: Requirements 10.5**

Property 15: 日志记录完整性
*For any* 工具调用，系统应该记录工具名称、参数、执行时间、结果摘要到日志
**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

Property 16: 返回数据结构化
*For any* 工具函数，返回值应该是有效的 JSON 对象
**Validates: Requirements 7.2**

Property 17: 掌握度计算正确性
*For any* 知识点数据，掌握度百分比应该等于 (correct_count / total_count) * 100
**Validates: Requirements 2.3**

Property 18: 薄弱知识点识别
*For any* 知识点数据，如果掌握度 < 0.6，该知识点应该被标识为薄弱知识点
**Validates: Requirements 2.3**

Property 19: 班级相对位置计算
*For any* 学生成绩和班级统计数据，学生的相对位置应该正确计算（排名 / 总人数）
**Validates: Requirements 5.3**

Property 20: 坐标信息保留
*For any* 包含批注坐标的错题记录，坐标信息应该被完整保留在返回结果中
**Validates: Requirements 3.5**

## Error Handling

### 错误类型

1. **工具不存在错误**
   - 场景：LLM 请求调用不存在的工具
   - 处理：返回错误信息，提示工具不存在
   - 降级：使用通用回复，不调用工具

2. **参数验证错误**
   - 场景：工具参数不符合 schema 定义
   - 处理：返回参数错误信息
   - 降级：使用默认参数或跳过该工具调用

3. **权限错误**
   - 场景：学生尝试查询其他学生的数据
   - 处理：返回权限拒绝错误
   - 降级：不返回任何数据

4. **数据库查询错误**
   - 场景：数据库连接失败或查询异常
   - 处理：记录错误日志，返回空结果
   - 降级：使用缓存数据（如果有）

5. **超时错误**
   - 场景：工具执行时间超过 5 秒
   - 处理：取消查询，返回超时错误
   - 降级：返回部分结果或提示稍后重试

6. **LLM 调用错误**
   - 场景：LLM API 调用失败
   - 处理：记录错误，返回通用错误消息
   - 降级：使用规则based 回复

### 错误日志格式

```python
{
    "timestamp": "2026-02-01T12:00:00Z",
    "level": "ERROR",
    "component": "ToolExecutor",
    "tool_name": "get_grading_history",
    "student_id": "s-001",
    "error_type": "DatabaseQueryError",
    "error_message": "Connection timeout",
    "stack_trace": "...",
    "execution_time_ms": 5000
}
```

## Testing Strategy

### Unit Testing

使用 pytest 进行单元测试，覆盖以下模块：

1. **Tool Functions**
   - 测试每个工具函数的基本功能
   - 测试参数验证
   - 测试错误处理
   - 测试边界情况（空数据、大数据量）

2. **Tool Registry**
   - 测试工具注册
   - 测试工具查询
   - 测试 schema 转换

3. **Tool Executor**
   - 测试单个工具执行
   - 测试并行执行
   - 测试超时处理
   - 测试权限验证

4. **LLM Client**
   - 测试 function calling 请求构建
   - 测试响应解析
   - 测试错误处理

### Property-Based Testing

使用 Hypothesis 进行属性测试，验证通用属性：

**测试库：** Hypothesis (Python)

**配置：** 每个属性测试运行至少 100 次迭代

**标记格式：** 每个属性测试必须包含注释：`# Feature: student-assistant-function-calling, Property {number}: {property_text}`

**示例：**

```python
# tests/property/test_tool_functions.py

from hypothesis import given, strategies as st
import pytest

# Feature: student-assistant-function-calling, Property 2: 返回数据完整性
@given(
    student_id=st.text(min_size=1, max_size=50),
    limit=st.integers(min_value=1, max_value=100)
)
@pytest.mark.asyncio
async def test_grading_history_returns_complete_data(student_id, limit):
    """测试 get_grading_history 返回完整数据"""
    result = await get_grading_history(student_id=student_id, limit=limit)
    
    # 验证返回结构
    assert isinstance(result, dict)
    assert "total" in result
    assert "records" in result
    assert isinstance(result["total"], int)
    assert isinstance(result["records"], list)
    
    # 验证每条记录的字段
    for record in result["records"]:
        assert "assignment_id" in record
        assert "assignment_title" in record
        assert "score" in record
        assert "max_score" in record
        assert "percentage" in record
        assert "graded_at" in record
        assert "feedback_summary" in record


# Feature: student-assistant-function-calling, Property 12: 分页限制
@given(
    student_id=st.text(min_size=1, max_size=50),
    limit=st.integers(min_value=1, max_value=50)
)
@pytest.mark.asyncio
async def test_grading_history_respects_limit(student_id, limit):
    """测试 get_grading_history 遵守 limit 参数"""
    result = await get_grading_history(student_id=student_id, limit=limit)
    
    # 返回结果数量不应超过 limit
    assert len(result["records"]) <= limit


# Feature: student-assistant-function-calling, Property 5: 权限控制
@given(
    student_a=st.text(min_size=1, max_size=50),
    student_b=st.text(min_size=1, max_size=50).filter(lambda x: x != student_a)
)
@pytest.mark.asyncio
async def test_tool_executor_enforces_permission(student_a, student_b):
    """测试工具执行器强制权限控制"""
    executor = ToolExecutor(registry)
    
    # 学生 A 尝试查询学生 B 的数据
    tool_call = ToolCall(
        id="call_1",
        name="get_grading_history",
        arguments={"student_id": student_b}
    )
    
    results = await executor.execute([tool_call], student_id=student_a)
    
    # 应该返回权限错误
    assert len(results) == 1
    assert results[0].error is not None
    assert "permission" in results[0].error.lower()
```

### Integration Testing

测试完整的 function calling 流程：

1. **端到端测试**
   - 模拟学生发送消息
   - 验证 LLM 选择正确的工具
   - 验证工具执行并返回数据
   - 验证最终响应包含数据

2. **多工具调用测试**
   - 测试需要多个工具的复杂查询
   - 验证工具按正确顺序执行
   - 验证数据正确整合

3. **性能测试**
   - 测试并行执行性能
   - 测试缓存效果
   - 测试超时处理

### Test Coverage Goals

- 单元测试覆盖率：> 80%
- 属性测试：覆盖所有核心属性
- 集成测试：覆盖主要用户场景

