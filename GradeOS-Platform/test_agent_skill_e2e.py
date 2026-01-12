"""
Agent Skill 端到端测试

使用根目录下的 学生作答.pdf 和 批改标准.pdf 测试完整的 Agent Skill 流程：
1. 上传批改标准 PDF → rubric_parse 节点解析并注册到 RubricRegistry
2. 上传学生作答 PDF → grade_batch 节点识别题目
3. 使用 GradingSkills.get_rubric_for_question 获取指定题目的评分标准
4. 基于指定评分标准进行批改
"""

import asyncio
import os
import sys
import json
import httpx
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# 测试文件路径
PROJECT_ROOT = Path(__file__).parent.parent
STUDENT_ANSWER_PDF = PROJECT_ROOT / "学生作答.pdf"
RUBRIC_PDF = PROJECT_ROOT / "批改标准.pdf"

API_BASE = "http://localhost:8001"


async def test_upload_with_rubric():
    """测试上传学生作答和批改标准"""
    print("\n" + "=" * 60)
    print("Agent Skill 端到端测试")
    print("=" * 60)
    
    # 检查文件是否存在
    if not STUDENT_ANSWER_PDF.exists():
        print(f"❌ 学生作答文件不存在: {STUDENT_ANSWER_PDF}")
        return False
    
    if not RUBRIC_PDF.exists():
        print(f"❌ 批改标准文件不存在: {RUBRIC_PDF}")
        return False
    
    print(f"✅ 学生作答文件: {STUDENT_ANSWER_PDF}")
    print(f"✅ 批改标准文件: {RUBRIC_PDF}")
    
    # 上传文件
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("\n📤 上传文件到后端...")
        
        with open(STUDENT_ANSWER_PDF, "rb") as exam_file, \
             open(RUBRIC_PDF, "rb") as rubric_file:
            
            files = [
                ("files", ("学生作答.pdf", exam_file, "application/pdf")),
                ("rubrics", ("批改标准.pdf", rubric_file, "application/pdf")),
            ]
            
            response = await client.post(
                f"{API_BASE}/batch/submit",
                files=files,
            )
        
        if response.status_code != 200:
            print(f"❌ 上传失败: {response.status_code}")
            print(response.text)
            return False
        
        result = response.json()
        batch_id = result.get("batch_id")
        print(f"✅ 上传成功: batch_id={batch_id}")
        print(f"   总页数: {result.get('total_pages')}")
        print(f"   预计完成时间: {result.get('estimated_completion_time')}秒")
        
        # 等待批改完成
        print("\n⏳ 等待批改完成...")
        
        # 使用 WebSocket 监听进度
        import websockets
        
        ws_url = f"ws://localhost:8001/batch/ws/{batch_id}"
        
        try:
            async with websockets.connect(ws_url) as ws:
                while True:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=60.0)
                        data = json.loads(message)
                        
                        msg_type = data.get("type")
                        
                        if msg_type == "progress":
                            stage = data.get("stage", "")
                            percentage = data.get("percentage", 0)
                            message_text = data.get("message", "")
                            print(f"   [{percentage:.0f}%] {stage}: {message_text}")
                            
                            # 检查 Agent Skill 日志
                            if "Agent Skill" in message_text or "get_rubric_for_question" in message_text:
                                print(f"   🔥 Agent Skill 触发: {message_text}")
                        
                        elif msg_type == "completed":
                            print("\n✅ 批改完成!")
                            results = data.get("results", [])
                            print(f"   学生数: {len(results)}")
                            
                            for r in results:
                                print(f"\n   学生: {r.get('studentName', 'Unknown')}")
                                print(f"   总分: {r.get('totalScore', 0)}/{r.get('maxScore', 0)}")
                                
                                # 检查 skill_logs
                                for q in r.get("questions", []):
                                    skill_logs = q.get("skill_logs", [])
                                    if skill_logs:
                                        print(f"   🔥 题目 {q.get('questionId')}: Agent Skill 调用 {len(skill_logs)} 次")
                                        for log in skill_logs:
                                            print(f"      - {log}")
                            
                            break
                        
                        elif msg_type == "error":
                            print(f"\n❌ 错误: {data.get('message')}")
                            break
                    
                    except asyncio.TimeoutError:
                        print("⏰ 等待超时")
                        break
        
        except Exception as e:
            print(f"WebSocket 连接失败: {e}")
            # 降级：轮询状态
            print("降级为轮询模式...")
            await asyncio.sleep(30)
        
        return True


async def test_skill_registry_directly():
    """直接测试 RubricRegistry 和 GradingSkills"""
    print("\n" + "=" * 60)
    print("直接测试 RubricRegistry 和 GradingSkills")
    print("=" * 60)
    
    from src.services.rubric_registry import RubricRegistry
    from src.skills.grading_skills import GradingSkills, create_grading_skills, get_skill_registry
    from src.models.grading_models import QuestionRubric, ScoringPoint
    
    # 创建 RubricRegistry
    registry = RubricRegistry(total_score=100.0)
    
    # 注册一些测试题目
    test_rubrics = [
        QuestionRubric(
            question_id="1",
            question_text="选择题",
            max_score=20,
            scoring_points=[
                ScoringPoint(description="第1小题正确", score=5, is_required=True),
                ScoringPoint(description="第2小题正确", score=5, is_required=True),
                ScoringPoint(description="第3小题正确", score=5, is_required=True),
                ScoringPoint(description="第4小题正确", score=5, is_required=True),
            ],
            standard_answer="1.B 2.A 3.C 4.D",
        ),
        QuestionRubric(
            question_id="2",
            question_text="填空题",
            max_score=20,
            scoring_points=[
                ScoringPoint(description="第1空正确", score=5, is_required=True),
                ScoringPoint(description="第2空正确", score=5, is_required=True),
                ScoringPoint(description="第3空正确", score=5, is_required=True),
                ScoringPoint(description="第4空正确", score=5, is_required=True),
            ],
            standard_answer="1.光合作用 2.细胞膜 3.DNA 4.线粒体",
        ),
        QuestionRubric(
            question_id="3",
            question_text="简答题：请简述细胞分裂的过程",
            max_score=30,
            scoring_points=[
                ScoringPoint(description="提到有丝分裂", score=5, is_required=True),
                ScoringPoint(description="提到减数分裂", score=5, is_required=True),
                ScoringPoint(description="描述有丝分裂的四个阶段", score=10, is_required=True),
                ScoringPoint(description="描述细胞分裂的意义", score=10, is_required=False),
            ],
            standard_answer="细胞分裂包括有丝分裂和减数分裂...",
            grading_notes="部分正确可给部分分",
        ),
    ]
    
    registry.register_rubrics(test_rubrics)
    print(f"✅ 已注册 {len(test_rubrics)} 道题目到 RubricRegistry")
    
    # 创建 GradingSkills
    skills = create_grading_skills(rubric_registry=registry)
    print("✅ 已创建 GradingSkills 实例")
    
    # 测试 get_rubric_for_question
    print("\n📝 测试 get_rubric_for_question Skill:")
    
    for q_id in ["1", "2", "3", "99"]:
        result = await skills.get_rubric_for_question(
            question_id=q_id,
            registry=registry
        )
        
        if result.success:
            data = result.data
            print(f"\n   题目 {q_id}:")
            print(f"   - is_default: {data.is_default}")
            print(f"   - confidence: {data.confidence:.2f}")
            if data.rubric:
                print(f"   - max_score: {data.rubric.max_score}")
                print(f"   - scoring_points: {len(data.rubric.scoring_points)}")
        else:
            print(f"\n   题目 {q_id}: ❌ 获取失败 - {result.error}")
    
    # 检查 Skill 调用日志
    skill_registry = get_skill_registry()
    logs = skill_registry.get_logs(limit=10)
    
    print(f"\n📊 Skill 调用日志 (最近 {len(logs)} 条):")
    for log in logs:
        print(f"   [{log.timestamp}] {log.skill_name}: success={log.success}, time={log.execution_time_ms:.2f}ms")
    
    return True


async def main():
    """主测试函数"""
    print("=" * 60)
    print("GradeOS Agent Skill 端到端测试")
    print("=" * 60)
    
    # 测试 1: 直接测试 RubricRegistry 和 GradingSkills
    try:
        await test_skill_registry_directly()
    except Exception as e:
        print(f"❌ 直接测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试 2: 通过 API 上传文件测试
    try:
        await test_upload_with_rubric()
    except Exception as e:
        print(f"❌ API 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
