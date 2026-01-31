"""测试批改历史图片 API"""

import asyncio
import requests
import json

API_BASE = "http://localhost:8001/api"

async def test_get_images():
    """测试获取批改历史图片"""
    
    # 1. 测试获取所有图片
    history_id = "6456cf62-523b-4fea-b7e6-055d6e0feb66"
    
    print(f"\n=== 测试 1: 获取批改历史图片 ===")
    print(f"History ID: {history_id}")
    
    response = requests.get(f"{API_BASE}/grading/history/{history_id}/images")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 成功获取图片")
        print(f"   - Student Key: {data['student_key']}")
        print(f"   - 图片数量: {len(data['images'])}")
        
        # 显示前 3 张图片的信息
        for i, img in enumerate(data['images'][:3]):
            base64_len = len(img['image_base64'])
            print(f"   - 图片 {i}: page_index={img['page_index']}, "
                  f"format={img['image_format']}, "
                  f"base64_size={base64_len} chars (~{base64_len * 3 // 4 // 1024} KB)")
    else:
        print(f"❌ 获取图片失败: {response.status_code}")
        print(f"   错误: {response.text}")
    
    # 2. 测试获取单张图片
    print(f"\n=== 测试 2: 获取单张图片 ===")
    student_key = "学生1"
    page_index = 0
    
    response = requests.get(
        f"{API_BASE}/grading/history/{history_id}/images/{student_key}/{page_index}"
    )
    
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type')
        content_length = len(response.content)
        print(f"✅ 成功获取单张图片")
        print(f"   - Content-Type: {content_type}")
        print(f"   - 大小: {content_length} bytes (~{content_length // 1024} KB)")
        
        # 保存图片到文件
        output_file = f"temp/test_image_page_{page_index}.png"
        with open(output_file, 'wb') as f:
            f.write(response.content)
        print(f"   - 已保存到: {output_file}")
    else:
        print(f"❌ 获取单张图片失败: {response.status_code}")
        print(f"   错误: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_get_images())
