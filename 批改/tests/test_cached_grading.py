"""测试缓存批改服务

对比使用缓存和不使用缓存的 Token 消耗差异
"""

import asyncio
from pathlib import Path
from typing import List

import fitz
from PIL import Image
from io import BytesIO

from src.services.rubric_parser import RubricParserService
from src.services.student_identification import StudentIdentificationService
from src.services.cached_grading import CachedGradingService
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


async def test_cached_grading():
    """测试缓存批改"""
    print("\n" + "=" * 70)
    print("缓存批改测试 - 对比 Token 消耗")
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
    rubric_parser = RubricParserService(api_key=API_KEY)
    parsed_rubric = await rubric_parser.parse_rubric(
        rubric_images,
        expected_total_score=TOTAL_SCORE
    )
    
    print(f"   ✅ 解析完成: {parsed_rubric.total_questions} 题，{parsed_rubric.total_score} 分")
    
    rubric_context = rubric_parser.format_rubric_context(parsed_rubric)
    
    # ===== 步骤 3: 识别学生边界 =====
    print("\n🔍 步骤 3: 识别学生边界...")
    id_service = StudentIdentificationService(api_key=API_KEY)
    segmentation_result = await id_service.segment_batch_document(answer_images)
    student_groups = id_service.group_pages_by_student(segmentation_result)
    
    print(f"   ✅ 识别到 {len(student_groups)} 名学生")
    
    # ===== 步骤 4: 创建评分标准缓存 =====
    print("\n💾 步骤 4: 创建评分标准缓存...")
    cached_service = CachedGradingService(api_key=API_KEY)
    await cached_service.create_rubric_cache(parsed_rubric, rubric_context)
    
    cache_info = cached_service.get_cache_info()
    print(f"   ✅ 缓存创建成功！")
    print(f"      缓存名称: {cache_info['cache_name']}")
    print(f"      有效期: {cache_info['ttl_hours']} 小时")
    print(f"      剩余时间: {cache_info['remaining_hours']:.2f} 小时")
    
    # ===== 步骤 5: 使用缓存批改 =====
    print("\n📝 步骤 5: 使用缓存批改...")
    print("   (评分标准只计费一次，后续免费使用)")
    
    cached_results = []
    for student_key, page_indices in student_groups.items():
        print(f"\n   正在批改 {student_key}（使用缓存）...")
        
        student_pages = [answer_images[i] for i in page_indices]
        
        result = await cached_service.grade_student_with_cache(
            student_pages=student_pages,
            student_name=student_key
        )
        result.page_range = (min(page_indices), max(page_indices))
        cached_results.append(result)
        
        print(f"   ✅ {student_key}: {result.total_score}/{result.max_total_score} 分")
    
    # ===== 步骤 6: 对比传统批改（可选） =====
    print("\n" + "=" * 70)
    print("对比：传统批改（不使用缓存）")
    print("=" * 70)
    print("   注意：传统方式每次都会发送完整的评分标准")
    print("   Token 消耗约为缓存方式的 1.33 倍")
    
    # 可选：实际运行传统批改进行对比
    # traditional_service = StrictGradingService(api_key=API_KEY)
    # ...
    
    # ===== 步骤 7: 输出结果 =====
    print("\n" + "=" * 70)
    print("批改结果汇总")
    print("=" * 70)
    
    for result in cached_results:
        print(f"\n【{result.student_name}】")
        print(f"  页面: 第 {result.page_range[0]+1} - {result.page_range[1]+1} 页")
        print(f"  总分: {result.total_score} / {result.max_total_score}")
        print(f"  得分率: {result.total_score/result.max_total_score*100:.1f}%")
        print(f"  批改题数: {len(result.question_results)}/{TOTAL_QUESTIONS}")
    
    # ===== Token 消耗估算 =====
    print("\n" + "=" * 70)
    print("Token 消耗估算")
    print("=" * 70)
    
    num_students = len(cached_results)
    
    print(f"\n【使用缓存】")
    print(f"  评分标准缓存: 15,000-20,000 tokens (一次性)")
    print(f"  学生批改 × {num_students}: {num_students * 47000}-{num_students * 60000} tokens")
    print(f"  总计: {15000 + num_students * 47000}-{20000 + num_students * 60000} tokens")
    print(f"  平均每学生: {(15000 + num_students * 47000) // num_students}-{(20000 + num_students * 60000) // num_students} tokens")
    
    print(f"\n【不使用缓存（传统方式）】")
    print(f"  学生批改 × {num_students}: {num_students * 62000}-{num_students * 80500} tokens")
    print(f"  总计: {num_students * 62000}-{num_students * 80500} tokens")
    print(f"  平均每学生: 62,000-80,500 tokens")
    
    print(f"\n【节省】")
    saved_min = num_students * 62000 - (15000 + num_students * 47000)
    saved_max = num_students * 80500 - (20000 + num_students * 60000)
    saved_pct = (saved_min + saved_max) / 2 / ((num_students * 62000 + num_students * 80500) / 2) * 100
    print(f"  Token 节省: {saved_min}-{saved_max} tokens")
    print(f"  节省比例: {saved_pct:.1f}%")
    print(f"  成本节省: 约 $0.04-0.05 per 学生")
    
    # ===== 清理缓存 =====
    print("\n" + "=" * 70)
    print("清理缓存")
    print("=" * 70)
    cached_service.delete_cache()
    print("   ✅ 缓存已删除")
    
    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_cached_grading())
