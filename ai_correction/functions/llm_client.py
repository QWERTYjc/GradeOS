#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 客户端 - 支持 OpenRouter, Gemini, OpenAI
"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    LLM_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL
)


class LLMClient:
    """统一的 LLM 客户端"""
    
    def __init__(self, provider=None, api_key=None, model=None):
        self.provider = provider or LLM_PROVIDER
        self.api_key = api_key
        self.model = model
        
        # 根据 provider 设置默认值
        if self.provider == 'openrouter':
            self.api_key = self.api_key or OPENROUTER_API_KEY
            self.model = self.model or OPENROUTER_MODEL
            self.base_url = OPENROUTER_BASE_URL
        elif self.provider == 'gemini':
            self.api_key = self.api_key or GEMINI_API_KEY
            self.model = self.model or GEMINI_MODEL
        elif self.provider == 'openai':
            self.api_key = self.api_key or OPENAI_API_KEY
            self.model = self.model or OPENAI_MODEL
        
        print(f"🤖 LLM Client 初始化: provider={self.provider}, model={self.model}")
    
    def chat(self, messages, temperature=0.7, max_tokens=2000):
        """
        统一的聊天接口
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大 token 数
        
        Returns:
            str: LLM 的回复
        """
        if self.provider == 'openrouter':
            return self._chat_openrouter(messages, temperature, max_tokens)
        elif self.provider == 'gemini':
            return self._chat_gemini(messages, temperature, max_tokens)
        elif self.provider == 'openai':
            return self._chat_openai(messages, temperature, max_tokens)
        else:
            raise ValueError(f"不支持的 LLM provider: {self.provider}")
    
    def _chat_openrouter(self, messages, temperature, max_tokens):
        """使用 OpenRouter API"""
        try:
            import requests
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/QWERTYjc/aiguru2.0",
                "X-Title": "AI Correction System"
            }
            
            data = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            print(f"📡 调用 OpenRouter API: model={self.model}")
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            
            response.raise_for_status()
            result = response.json()
            
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                print(f"✅ OpenRouter 响应成功: {len(content)} 字符")
                return content
            else:
                raise ValueError(f"OpenRouter 响应格式错误: {result}")
                
        except Exception as e:
            print(f"❌ OpenRouter API 调用失败: {e}")
            raise
    
    def _chat_gemini(self, messages, temperature, max_tokens):
        """使用 Gemini API"""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            
            # 转换消息格式
            prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
            
            print(f"📡 调用 Gemini API: model={self.model}")
            
            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': temperature,
                    'max_output_tokens': max_tokens
                }
            )
            
            content = response.text
            print(f"✅ Gemini 响应成功: {len(content)} 字符")
            return content
            
        except Exception as e:
            print(f"❌ Gemini API 调用失败: {e}")
            raise
    
    def _chat_openai(self, messages, temperature, max_tokens):
        """使用 OpenAI API"""
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            
            print(f"📡 调用 OpenAI API: model={self.model}")
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            print(f"✅ OpenAI 响应成功: {len(content)} 字符")
            return content
            
        except Exception as e:
            print(f"❌ OpenAI API 调用失败: {e}")
            raise


def get_llm_client(provider=None, api_key=None, model=None):
    """获取 LLM 客户端实例"""
    return LLMClient(provider=provider, api_key=api_key, model=model)


# 测试代码
if __name__ == '__main__':
    # 测试 OpenRouter
    print("=" * 60)
    print("🧪 测试 LLM Client")
    print("=" * 60)
    
    client = get_llm_client()
    
    messages = [
        {"role": "user", "content": "请用一句话介绍 Python 编程语言。"}
    ]
    
    try:
        response = client.chat(messages)
        print(f"\n📝 LLM 回复:\n{response}\n")
        print("✅ 测试成功！")
    except Exception as e:
        print(f"❌ 测试失败: {e}")

