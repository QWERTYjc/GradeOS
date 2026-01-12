#!/usr/bin/env python3
"""
批改工作流优化 - 演示脚本

演示新工作流的核心功能：
1. 跨页题目检测与合并
2. 得分点明细评分
3. 学生边界检测
4. 结果聚合与导出
"""

import json
from src.models.grading_models import (
    QuestionRubric,
    ScoringPoint,
    QuestionResult,
    ScoringPointResult,
    PageGradingResult,
    StudentResult,
    CrossPageQuestion,
    BatchGradingResult,
    StudentInfo,
)


def demo_scoring_point_details():
    """演示得分点明细功能"""
    print("\n" + "=" * 60)
    print("演示 1: 得分点明细评分")
    print("=" * 60)

    # 创建得分点
    sp1 = ScoringPoint(description="理解题意", score=2.0, is_required=True)
    sp2 = ScoringPoint(description="列式正确", score=3.0, is_required=True)
    sp3 = ScoringPoint(description="计算无误", score=2.0, is_required=True)

    # 创建得分点评分结果
    spr1 = ScoringPointResult(scoring_point=sp1, awarded=2.0, evidence="学生正确理解了题意")
    spr2 = ScoringPointResult(scoring_point=sp2, awarded=2.5, evidence="列式基本正确，但有一处符号错误")
    spr3 = ScoringPointResult(scoring_point=sp3, awarded=2.0, evidence="计算过程正确")

    # 创建题目结果
    question = QuestionResult(
        question_id="1",
        score=6.5,
        max_score=7.0,
        confidence=0.92,
        feedback="总体不错，注意符号的使用",
        scoring_point_results=[spr1, spr2, spr3],
    )

    print(f"\n题目编号: {question.question_id}")
    print(f"得分: {question.score}/{question.max_score}")
    print(f"置信度: {question.confidence * 100:.0f}%")
    print(f"\n得分点明细:")
    for i, spr in enumerate(question.scoring_point_results, 1):
        print(f"  {i}. {spr.scoring_point.description}")
        print(f"     获得分数: {spr.awarded}/{spr.scoring_point.score}")
        print(f"     评分依据: {spr.evidence}")

    return question


def demo_cross_page_questions():
    """演示跨页题目检测与合并"""
    print("\n" + "=" * 60)
    print("演示 2: 跨页题目检测与合并")
    print("=" * 60)

    # 创建跨页题目信息
    cpq = CrossPageQuestion(
        question_id="7",
        page_indices=[2, 3],
        confidence=0.88,
        merge_reason="题目内容跨越第2页和第3页，需要合并评分",
    )

    print(f"\n题目编号: {cpq.question_id}")
    print(f"涉及页面: {[p + 1 for p in cpq.page_indices]}")
    print(f"合并置信度: {cpq.confidence * 100:.0f}%")
    print(f"合并原因: {cpq.merge_reason}")

    # 创建合并后的题目结果
    merged_question = QuestionResult(
        question_id="7",
        score=8.0,
        max_score=10.0,
        confidence=0.85,
        feedback="跨页题目，已合并评分",
        page_indices=[2, 3],
        is_cross_page=True,
        merge_source=["page_2_q7_part1", "page_3_q7_part2"],
    )

    print(f"\n合并后的题目结果:")
    print(f"  得分: {merged_question.score}/{merged_question.max_score}")
    print(f"  页面: {[p + 1 for p in merged_question.page_indices]}")
    print(f"  是否跨页: {'是' if merged_question.is_cross_page else '否'}")
    print(f"  合并来源: {merged_question.merge_source}")

    return cpq, merged_question


def demo_student_boundary_detection():
    """演示学生边界检测"""
    print("\n" + "=" * 60)
    print("演示 3: 学生边界检测与聚合")
    print("=" * 60)

    # 创建学生结果
    student1 = StudentResult(
        student_key="student_001",
        student_id="S001",
        student_name="张三",
        start_page=0,
        end_page=2,
        total_score=85.5,
        max_total_score=100.0,
        confidence=0.92,
        needs_confirmation=False,
        question_results=[
            QuestionResult(
                question_id="1",
                score=10.0,
                max_score=10.0,
                confidence=0.95,
                feedback="完全正确",
                page_indices=[0],
            ),
            QuestionResult(
                question_id="2",
                score=8.5,
                max_score=10.0,
                confidence=0.88,
                feedback="基本正确",
                page_indices=[1],
            ),
            QuestionResult(
                question_id="7",
                score=8.0,
                max_score=10.0,
                confidence=0.85,
                feedback="跨页题目，已合并评分",
                page_indices=[1, 2],
                is_cross_page=True,
            ),
        ],
    )

    student2 = StudentResult(
        student_key="student_002",
        student_id="S002",
        student_name="李四",
        start_page=3,
        end_page=5,
        total_score=72.0,
        max_total_score=100.0,
        confidence=0.78,
        needs_confirmation=True,  # 低置信度，需要人工确认
        question_results=[
            QuestionResult(
                question_id="3",
                score=7.0,
                max_score=10.0,
                confidence=0.75,
                feedback="有一处计算错误",
                page_indices=[3],
            ),
            QuestionResult(
                question_id="4",
                score=8.0,
                max_score=10.0,
                confidence=0.82,
                feedback="思路正确",
                page_indices=[4],
            ),
        ],
    )

    print(f"\n学生 1: {student1.student_name}")
    print(f"  学号: {student1.student_id}")
    print(f"  页面范围: {student1.start_page + 1} - {student1.end_page + 1}")
    print(f"  总分: {student1.total_score}/{student1.max_total_score}")
    print(f"  置信度: {student1.confidence * 100:.0f}%")
    print(f"  需要确认: {'是' if student1.needs_confirmation else '否'}")
    print(f"  题目数: {len(student1.question_results)}")
    for q in student1.question_results:
        cross_page_mark = " (跨页)" if q.is_cross_page else ""
        print(f"    - 第 {q.question_id} 题: {q.score}/{q.max_score}{cross_page_mark}")

    print(f"\n学生 2: {student2.student_name}")
    print(f"  学号: {student2.student_id}")
    print(f"  页面范围: {student2.start_page + 1} - {student2.end_page + 1}")
    print(f"  总分: {student2.total_score}/{student2.max_total_score}")
    print(f"  置信度: {student2.confidence * 100:.0f}%")
    print(f"  需要确认: {'是' if student2.needs_confirmation else '否'} ⚠️")
    print(f"  题目数: {len(student2.question_results)}")
    for q in student2.question_results:
        print(f"    - 第 {q.question_id} 题: {q.score}/{q.max_score}")

    return student1, student2


def demo_batch_grading_result():
    """演示批量批改结果"""
    print("\n" + "=" * 60)
    print("演示 4: 批量批改结果导出")
    print("=" * 60)

    # 创建批量批改结果
    batch_result = BatchGradingResult(
        batch_id="batch_20250101_001",
        total_pages=6,
        processed_pages=6,
        student_results=[
            StudentResult(
                student_key="student_001",
                student_id="S001",
                student_name="张三",
                start_page=0,
                end_page=2,
                total_score=85.5,
                max_total_score=100.0,
                confidence=0.92,
                needs_confirmation=False,
                question_results=[
                    QuestionResult(
                        question_id="1",
                        score=10.0,
                        max_score=10.0,
                        confidence=0.95,
                        feedback="完全正确",
                        page_indices=[0],
                    ),
                ],
            ),
            StudentResult(
                student_key="student_002",
                student_id="S002",
                student_name="李四",
                start_page=3,
                end_page=5,
                total_score=72.0,
                max_total_score=100.0,
                confidence=0.78,
                needs_confirmation=True,
                question_results=[
                    QuestionResult(
                        question_id="3",
                        score=7.0,
                        max_score=10.0,
                        confidence=0.75,
                        feedback="有一处计算错误",
                        page_indices=[3],
                    ),
                ],
            ),
        ],
        cross_page_questions=[
            CrossPageQuestion(
                question_id="7",
                page_indices=[1, 2],
                confidence=0.88,
                merge_reason="题目内容跨越第2页和第3页",
            ),
        ],
        errors=[],
    )

    print(f"\n批次ID: {batch_result.batch_id}")
    print(f"总页数: {batch_result.total_pages}")
    print(f"已处理: {batch_result.processed_pages}/{batch_result.total_pages}")
    print(f"学生数: {len(batch_result.student_results)}")
    print(f"跨页题目: {len(batch_result.cross_page_questions)}")
    print(f"错误数: {len(batch_result.errors)}")

    # 统计信息
    total_score = sum(s.total_score for s in batch_result.student_results)
    avg_score = total_score / len(batch_result.student_results)
    needs_confirm = sum(
        1 for s in batch_result.student_results if s.needs_confirmation
    )

    print(f"\n统计信息:")
    print(f"  平均分: {avg_score:.1f}")
    print(f"  待确认: {needs_confirm} 名学生")

    # 导出为 JSON
    print(f"\n导出为 JSON:")
    json_str = batch_result.to_json()
    print(json_str[:500] + "...\n")

    return batch_result


def main():
    """运行演示"""
    print("\n" + "🎯 " * 20)
    print("批改工作流优化 - 新功能演示")
    print("🎯 " * 20)

    # 演示 1: 得分点明细
    demo_scoring_point_details()

    # 演示 2: 跨页题目
    demo_cross_page_questions()

    # 演示 3: 学生边界检测
    demo_student_boundary_detection()

    # 演示 4: 批量批改结果
    demo_batch_grading_result()

    print("\n" + "=" * 60)
    print("✅ 所有演示完成！")
    print("=" * 60)
    print("\n新工作流特性总结:")
    print("  ✓ 得分点明细评分 - 详细记录每个得分点的评分情况")
    print("  ✓ 跨页题目检测 - 自动识别并合并跨页题目")
    print("  ✓ 学生边界检测 - 智能识别学生答卷范围")
    print("  ✓ 置信度标记 - 低置信度结果标记为待确认")
    print("  ✓ 完整数据导出 - 支持 JSON 序列化和反序列化")
    print("\n前端已支持显示:")
    print("  ✓ 跨页题目标记（紫色 Layers 图标）")
    print("  ✓ 得分点明细列表")
    print("  ✓ 页面索引信息")
    print("  ✓ 学生页面范围和置信度")
    print("  ✓ 待确认学生统计")
    print("\n访问应用:")
    print("  前端: http://localhost:3000")
    print("  后端: http://localhost:8001/docs")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
