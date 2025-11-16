"""调试Textin API响应格式"""
import os
import sys
from pathlib import Path
import json

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv('.env.local')

from functions.image_optimization.textin_client import TextinClient
from functions.image_optimization.models import APIParameters

def debug_api_response():
    """调试API响应格式"""
    test_image = "temp/uploads/test_homework.jpg"
    
    if not os.path.exists(test_image):
        print(f"❌ 测试图片不存在: {test_image}")
        return
    
    print("🔍 调试Textin API响应格式")
    print("=" * 70)
    
    try:
        client = TextinClient()
        
        # 读取图片
        with open(test_image, 'rb') as f:
            image_binary = f.read()
        
        # 构建请求
        params = APIParameters()
        url = client._build_url(params)
        headers = client._build_headers()
        
        print(f"\n📤 请求信息:")
        print(f"  URL: {url}")
        print(f"  图片大小: {len(image_binary)} bytes")
        
        # 发送请求
        response = client.session.post(url, headers=headers, data=image_binary, timeout=30)
        
        print(f"\n📥 响应信息:")
        print(f"  HTTP状态码: {response.status_code}")
        print(f"  响应大小: {len(response.content)} bytes")
        
        # 解析JSON
        response_data = response.json()
        
        print(f"\n📋 完整响应JSON:")
        print(json.dumps(response_data, indent=2, ensure_ascii=False))
        
        # 分析结构
        print(f"\n🔍 响应结构分析:")
        print(f"  code: {response_data.get('code')}")
        print(f"  message: {response_data.get('message')}")
        
        result = response_data.get('result', {})
        print(f"\n  result键: {list(result.keys())}")
        
        image_list = result.get('image_list', [])
        print(f"\n  image_list长度: {len(image_list)}")
        
        if image_list:
            first_item = image_list[0]
            print(f"  image_list[0]类型: {type(first_item)}")
            
            if isinstance(first_item, dict):
                print(f"  image_list[0]键: {list(first_item.keys())}")
                print(f"  完整内容: {first_item}")
            else:
                print(f"  image_list[0]前100字符: {str(first_item)[:100]}...")
        
        client.close()
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_api_response()
