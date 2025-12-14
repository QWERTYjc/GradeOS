"""单页测试 - 查看 Gemini 的原始响应"""

import asyncio
import base64
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage


async def test_single_page():
    """测试单页识别"""
    
    api_key = "AIzaSyD5D9_uYqcRgyivexpVq5iPvqL6uKD85QE"
    
    # 转换第一页
    import fitz
    from PIL import Image
    from io import BytesIO
    
    pdf_doc = fitz.open("学生作答.pdf")
    
    # 测试多个页面
    test_pages = [0, 1, 24, 25]  # 第 1, 2, 25, 26 页
    
    for page_idx in test_pages:
        print(f"\n{'='*60}")
        print(f"测试页面 {page_idx + 1}")
        print('='*60)
        
        page = pdf_doc[page_idx]
    
        mat = fitz.Matrix(300/72, 300/72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        image_data = img_bytes.getvalue()
    
        # 保存图像
        img_filename = f"test_page_{page_idx+1}.png"
        with open(img_filename, "wb") as f:
            f.write(image_data)
        print(f"✅ 已保存: {img_filename}")
        
            # 调用 Gemini
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.1
        )
        
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        prompt = """请分析这张试卷图像，识别学生信息区域。

查找以下信息（通常位于试卷顶部或右上角）：
- 学生姓名（可能是手写或印刷）
- 学号/考号（数字序列）
- 班级（如有）

请以 JSON 格式返回结果：
{
    "found": true/false,
    "student_info": {
        "name": "学生姓名或null",
        "student_id": "学号或null",
        "class_name": "班级或null",
        "confidence": 0.0-1.0,
        "bounding_box": [ymin, xmin, ymax, xmax] 或 null
    }
}

注意：
- 如果无法识别任何学生信息，设置 found=false
- confidence 表示识别的置信度（0-1）
- bounding_box 使用归一化坐标（0-1000 比例）
- 手写字迹模糊时，尽量识别但降低 confidence"""

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/png;base64,{image_b64}"
                }
            ]
        )
    
        print("🔍 调用 Gemini API...")
        response = await llm.ainvoke([message])
        
        print("\nGemini 响应:")
        print("-" * 60)
        print(response.content[:500])  # 只显示前 500 字符
        print("-" * 60)
        
        await asyncio.sleep(2)  # 避免 API 限流
    
    pdf_doc.close()


if __name__ == "__main__":
    asyncio.run(test_single_page())
