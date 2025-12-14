"""批量学生识别实测脚本 - 基于题目顺序循环检测"""

import asyncio
from pathlib import Path

from src.services.student_identification import StudentIdentificationService


async def main():
    """主测试函数"""
    
    api_key = "AIzaSyD5D9_uYqcRgyivexpVq5iPvqL6uKD85QE"
    student_answer_path = Path("学生作答.pdf")
    
    if not student_answer_path.exists():
        print(f"❌ 文件不存在: {student_answer_path}")
        return
    
    print("=" * 60)
    print("批量学生识别实测 - 基于题目顺序循环检测")
    print("=" * 60)
    
    # 转换 PDF 为图像
    print("\n📄 步骤 1: 转换 PDF 为图像...")
    import fitz
    from PIL import Image
    from io import BytesIO
    
    pdf_doc = fitz.open(str(student_answer_path))
    print(f"✅ PDF 共 {len(pdf_doc)} 页")
    
    # 处理全部页面
    max_pages = len(pdf_doc)
    print(f"   处理全部 {max_pages} 页...")
    
    images_data = []
    for page_num in range(max_pages):
        page = pdf_doc[page_num]
        mat = fitz.Matrix(200/72, 200/72)  # 200 DPI（加快处理）
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        images_data.append(img_bytes.getvalue())
    
    pdf_doc.close()
    print(f"✅ 转换完成")
    
    # 创建识别服务
    print("\n🔍 步骤 2: 初始化服务...")
    service = StudentIdentificationService(
        api_key=api_key,
        model_name="gemini-2.5-flash"
    )
    
    # 执行批量识别
    print("\n🎯 步骤 3: 分析页面并检测学生边界...")
    print("(基于题目顺序循环检测，无需学生信息)")
    print("-" * 60)
    
    try:
        result = await service.segment_batch_document(images_data)
        
        print("\n" + "=" * 60)
        print("识别结果")
        print("=" * 60)
        print(f"总页数: {result.total_pages}")
        print(f"识别到的学生数: {result.student_count}")
        print(f"未识别页数: {len(result.unidentified_pages)}")
        
        # 按学生分组
        groups = service.group_pages_by_student(result)
        
        print("\n" + "-" * 60)
        print("学生分组详情")
        print("-" * 60)
        
        for student_key, page_indices in groups.items():
            # 获取学生信息
            student_info = None
            for mapping in result.page_mappings:
                if mapping.page_index in page_indices:
                    student_info = mapping.student_info
                    break
            
            print(f"\n{student_key}:")
            if student_info:
                print(f"  姓名: {student_info.name}")
                print(f"  学号: {student_info.student_id}")
                print(f"  是否占位符: {student_info.is_placeholder}")
            print(f"  页面范围: {min(page_indices)+1} - {max(page_indices)+1}")
            print(f"  页数: {len(page_indices)}")
        
        print("\n" + "=" * 60)
        
        # 验证
        if result.student_count == 2:
            print("✅ 正确识别到 2 名学生！")
        else:
            print(f"⚠️  预期 2 名学生，实际 {result.student_count} 名")
        
        # 检查页面分配是否合理
        if len(groups) >= 2:
            pages_per_student = [len(pages) for pages in groups.values()]
            print(f"✅ 每个学生的页数: {pages_per_student}")
            
            # 49 页 / 2 学生 ≈ 24-25 页/人
            if all(20 <= p <= 30 for p in pages_per_student):
                print("✅ 页面分配合理（每人约 24-25 页）")
        
    except Exception as e:
        print(f"\n❌ 识别失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
