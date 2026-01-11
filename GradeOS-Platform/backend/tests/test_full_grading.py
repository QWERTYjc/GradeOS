"""完整批改流程测试 - 严格遵循评分标准

流程：
1. 解析批改标准（提取19道题的分值和得分点）
2. 识别学生边界（2名学生）
3. 逐题批改（严格按得分点评分）
4. 输出详细报告
"""

import asyncio
from pathlib import Path
from typing import List

import fitz
from PIL import Image
from io import BytesIO

from src.services.student_identification import StudentIdentificationService
from src.services.rubric_parser import RubricParserService
from src.services.strict_grading import StrictGradingService


API_KEY = "AIzaSyD5D9_uYqcRgyivexpVq5iPvqL6uKD85QE"
TOTAL_SCORE = 105
TOTAL_QUESTIONS = 19


def pdf_to_images(pdf_path: str, dpi: int = 150) -> List[bytes]:
    """将 PDF 转换为图像列表"""
    pdf_doc = fitz.open(pdf_path)
    images = []
    
    for page_num in range(len(pdf_doc)):
        page = pdf_doc[page_num]
        mat = fitz.Matrix(dpi/72, dpi/72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        images.append(img_bytes.getvalue())
    
    pdf_doc.close()
    return images


async def main():
    """主函数"""
    print("=" * 70)
    print("完整批改流程测试 - 严格遵循评分标准")
    print("=" * 70)
    print(f"预期: {TOTAL_QUESTIONS} 道题，总分 {TOTAL_SCORE} 分，2 名学生")
    print("=" * 70)
    
    rubric_path = Path("批改标准.pdf")
    answer_path = Path("学生作答.pdf")
    
    if not rubric_path.exists() or not answer_path.exists():
        print("❌ 缺少必要文件")
        return
    
    # ===== 步骤 1: 读取文件 =====
    print("\n📚 步骤 1: 读取文件...")
    rubric_images = pdf_to_images(str(rubric_path), dpi=150)
    answer_images = pdf_to_images(str(answer_path), dpi=150)
    print(f"   批改标准: {len(rubric_images)} 页")
    print(f"   学生作答: {len(answer_images)} 页")
    
    # ===== 步骤 2: 解析批改标准 =====
    print("\n📋 步骤 2: 解析批改标准...")
    print("   (提取每道题的分值、得分点、另类解法)")
    
    rubric_parser = RubricParserService(api_key=API_KEY)
    parsed_rubric = await rubric_parser.parse_rubric(rubric_images)
    
    print(f"\n   ✅ 解析完成:")
    print(f"      题目数: {parsed_rubric.total_questions}")
    print(f"      总分: {parsed_rubric.total_score}")
    print(f"      格式: {parsed_rubric.rubric_format}")
    
    # 显示各题分值
    print("\n   各题分值:")
    for q in parsed_rubric.questions:
        alt_count = len(q.alternative_solutions)
        alt_note = f" (+{alt_count}种另类解法)" if alt_count > 0 else ""
        print(f"      第{q.question_id}题: {q.max_score}分 ({len(q.scoring_points)}个得分点){alt_note}")
    
    # 验证总分
    actual_total = sum(q.max_score for q in parsed_rubric.questions)
    if abs(actual_total - TOTAL_SCORE) > 1:
        print(f"\n   ⚠️  总分不匹配: 预期 {TOTAL_SCORE}, 实际 {actual_total}")
    
    # 生成评分标准上下文
    rubric_context = rubric_parser.format_rubric_context(parsed_rubric)
    
    # ===== 步骤 3: 识别学生边界 =====
    print("\n🔍 步骤 3: 识别学生边界...")
    
    id_service = StudentIdentificationService(api_key=API_KEY)
    segmentation_result = await id_service.segment_batch_document(answer_images)
    student_groups = id_service.group_pages_by_student(segmentation_result)
    
    print(f"   ✅ 识别到 {len(student_groups)} 名学生:")
    for student_key, pages in student_groups.items():
        print(f"      {student_key}: 第 {min(pages)+1} - {max(pages)+1} 页 ({len(pages)} 页)")
    
    # ===== 步骤 4: 批改每个学生 =====
    print("\n📝 步骤 4: 开始批改...")
    print("   (严格按照得分点评分)")
    
    grading_service = StrictGradingService(api_key=API_KEY)
    all_results = []
    
    for student_key, page_indices in student_groups.items():
        print(f"\n   正在批改 {student_key}...")
        
        # 获取该学生的页面
        student_pages = [answer_images[i] for i in page_indices]
        
        # 批改
        result = await grading_service.grade_student(
            student_pages=student_pages,
            rubric=parsed_rubric,
            rubric_context=rubric_context,
            student_name=student_key
        )
        result.page_range = (min(page_indices), max(page_indices))
        all_results.append(result)
        
        print(f"   ✅ {student_key}: {result.total_score}/{result.max_total_score} 分")
        print(f"      批改题数: {len(result.question_results)}")
    
    # ===== 步骤 5: 输出详细报告 =====
    print("\n" + "=" * 70)
    print("详细批改报告")
    print("=" * 70)
    
    for result in all_results:
        report = grading_service.format_grading_report(result, detailed=True)
        print(report)
    
    # ===== 汇总 =====
    print("\n" + "=" * 70)
    print("批改汇总")
    print("=" * 70)
    
    for result in all_results:
        print(f"\n【{result.student_name}】")
        print(f"  页面: 第 {result.page_range[0]+1} - {result.page_range[1]+1} 页")
        print(f"  总分: {result.total_score} / {result.max_total_score}")
        print(f"  得分率: {result.total_score/result.max_total_score*100:.1f}%")
        print(f"  批改题数: {len(result.question_results)}/{TOTAL_QUESTIONS}")
        
        # 统计使用另类解法的题目
        alt_count = sum(1 for q in result.question_results if q.used_alternative_solution)
        if alt_count > 0:
            print(f"  使用另类解法: {alt_count} 题")
    
    print("\n" + "=" * 70)
    print("✅ 批改完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
