"""
Gemini Context Caching 使用示例

演示如何使用缓存批改服务来节省 Token 成本
"""

import asyncio
from pathlib import Path
from typing import List

import fitz
from PIL import Image
from io import BytesIO

from src.services.rubric_parser import RubricParserService
from src.services.cached_grading import CachedGradingService
from src.services.student_identification import StudentIdentificationService


# 配置
API_KEY = "YOUR_API_KEY_HERE"  # 替换为你的 API Key
RUBRIC_PDF = "批改标准.pdf"
ANSWER_PDF = "学生作答.pdf"


def pdf_to_images(pdf_path: str) -> List[bytes]:
    """将 PDF 转换为图像列表"""
    doc = fitz.open(pdf_path)
    images = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        images.append(img_bytes.getvalue())
    
    return images


async def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("Gemini Context Caching 批改示例")
    print("=" * 70)
    
    # 第一步：加载 PDF
    print("\n📄 加载 PDF 文件...")
    rubric_images = pdf_to_images(RUBRIC_PDF)
    answer_images = pdf_to_images(ANSWER_PDF)
    print(f"   批改标准: {len(rubric_images)} 页")
    print(f"   学生作答: {len(answer_images)} 页")
    
    # 第二步：解析评分标准
    print("\n📋 解析评分标准...")
    rubric_parser = RubricParserService(api_key=API_KEY)
    parsed_rubric = await rubric_parser.parse_rubric(
        rubric_images=rubric_images,
        expected_total_score=105
    )
    rubric_context = rubric_parser.format_rubric_context(parsed_rubric)
    print(f"   ✅ 解析完成: {parsed_rubric.total_questions} 题, 总分 {parsed_rubric.total_score}")
    
    # 第三步：识别学生
    print("\n👥 识别学生...")
    student_service = StudentIdentificationService(api_key=API_KEY)
    students = await student_service.identify_students(
        answer_images=answer_images,
        total_questions=parsed_rubric.total_questions
    )
    print(f"   ✅ 识别到 {len(students)} 名学生")
    for student in students:
        print(f"      - {student.student_name}: 第 {student.start_page}-{student.end_page} 页")
    
    # 第四步：创建缓存批改服务
    print("\n💾 创建缓存批改服务...")
    cached_service = CachedGradingService(
        api_key=API_KEY,
        model_name="gemini-2.5-flash",
        cache_ttl_hours=1
    )
    
    # 第五步：创建评分标准缓存
    print("   正在创建评分标准缓存...")
    await cached_service.create_rubric_cache(parsed_rubric, rubric_context)
    
    cache_info = cached_service.get_cache_info()
    print(f"   ✅ 缓存创建成功！")
    print(f"      缓存名称: {cache_info['cache_name']}")
    print(f"      有效期: {cache_info['ttl_hours']} 小时")
    print(f"      剩余时间: {cache_info['remaining_hours']:.2f} 小时")
    
    # 第六步：批改所有学生（使用缓存）
    print("\n📝 开始批改（使用缓存）...")
    results = []
    
    for i, student in enumerate(students, 1):
        print(f"\n   [{i}/{len(students)}] 批改 {student.student_name}...")
        
        # 提取学生页面
        student_pages = answer_images[student.start_page-1:student.end_page]
        
        # 使用缓存批改
        result = await cached_service.grade_student_with_cache(
            student_pages=student_pages,
            student_name=student.student_name
        )
        
        results.append(result)
        
        print(f"      ✅ 批改完成: {result.total_score}/{result.max_total_score} 分")
        print(f"         批改题数: {len(result.question_results)} 题")
    
    # 第七步：显示结果
    print("\n" + "=" * 70)
    print("批改结果汇总")
    print("=" * 70)
    
    for result in results:
        print(f"\n{result.student_name}:")
        print(f"   总分: {result.total_score}/{result.max_total_score}")
        print(f"   批改题数: {len(result.question_results)}")
        
        # 显示前 3 题
        for q in result.question_results[:3]:
            print(f"   - 第 {q.question_id} 题: {q.awarded_score}/{q.max_score} 分")
    
    # 第八步：显示 Token 节省信息
    print("\n" + "=" * 70)
    print("Token 节省分析")
    print("=" * 70)
    
    # 估算 Token 消耗
    rubric_tokens = 15000  # 评分标准约 15,000 tokens
    per_student_tokens = 38000  # 每个学生约 38,000 tokens（不含评分标准）
    
    # 传统方式
    traditional_tokens = len(students) * (rubric_tokens + per_student_tokens)
    
    # 使用缓存
    cached_tokens = rubric_tokens + len(students) * per_student_tokens
    
    # 节省
    saved_tokens = traditional_tokens - cached_tokens
    saved_percentage = (saved_tokens / traditional_tokens) * 100
    
    print(f"\n传统方式:")
    print(f"   评分标准: {rubric_tokens:,} tokens × {len(students)} = {rubric_tokens * len(students):,} tokens")
    print(f"   学生作答: {per_student_tokens:,} tokens × {len(students)} = {per_student_tokens * len(students):,} tokens")
    print(f"   总计: {traditional_tokens:,} tokens")
    
    print(f"\n使用缓存:")
    print(f"   评分标准: {rubric_tokens:,} tokens × 1 = {rubric_tokens:,} tokens (缓存)")
    print(f"   学生作答: {per_student_tokens:,} tokens × {len(students)} = {per_student_tokens * len(students):,} tokens")
    print(f"   总计: {cached_tokens:,} tokens")
    
    print(f"\n节省:")
    print(f"   Token 节省: {saved_tokens:,} tokens ({saved_percentage:.1f}%)")
    print(f"   成本节省: 约 ${saved_tokens * 0.000001:.2f}")
    
    # 第九步：清理缓存
    print("\n🗑️  清理缓存...")
    cached_service.delete_cache()
    print("   ✅ 缓存已删除")
    
    print("\n" + "=" * 70)
    print("✅ 批改完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
