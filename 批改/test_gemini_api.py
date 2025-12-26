"""测试 Gemini API Key 配置"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取 API Key
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ 错误：未找到 GEMINI_API_KEY 环境变量")
    exit(1)

print(f"✅ API Key 已加载: {api_key[:20]}...")

# 测试 API 连接
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    print("\n测试 Gemini 2.5 Flash Lite...")
    model = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        google_api_key=api_key
    )
    response = model.invoke("你好，请用一句话介绍你自己")
    print(f"✅ 响应: {response.content}")
    
    print("\n✅ Gemini API 配置成功！")
    
except Exception as e:
    print(f"❌ API 测试失败: {e}")
    exit(1)
