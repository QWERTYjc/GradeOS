#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini 3 Pro 原生 SDK 客户端
完全移除 Vision API，使用 Gemini 原生多模态能力
参考文档: https://ai.google.dev/gemini-api/docs/gemini-3
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class LLMClient:
    """Gemini 3 Pro 原生 SDK 客户端"""
    
    def __init__(self, provider=None, api_key=None, model=None, fallback_model=None):
        """
        初始化 Gemini 3 Pro 客户端
        
        Args:
            provider: 忽略（强制使用 Gemini）
            api_key: Gemini API 密钥
            model: 模型名称（默认 gemini-3-pro-preview）
            fallback_model: 忽略
        """
        self.provider = "gemini"
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL or "gemini-3-pro-preview"
        self.last_call = None
        
        # 初始化 Gemini SDK
        try:
            from google import genai
            from google.genai import types
            
            self.client = genai.Client(
                api_key=self.api_key,
                http_options={'api_version': 'v1beta'}  # 使用 v1beta 以支持最新功能
            )
            self.types = types
            logger.info(f"✅ Gemini 3 Pro 客户端初始化成功: model={self.model}")
        except ImportError:
            error_msg = "❌ 请安装 Google GenAI SDK: pip install google-genai"
            logger.error(error_msg)
            raise ImportError(error_msg)
        except Exception as e:
            logger.error(f"❌ Gemini 客户端初始化失败: {e}")
            raise
    
    def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 1.0,  # Gemini 3 推荐使用默认值 1.0
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,  # 已弃用，使用 thinking_level
        timeout: Optional[int] = None,
        stream: bool = False,
        thinking_level: str = "high",  # Gemini 3 新参数
        files: Optional[List[str]] = None,  # PDF 文件路径列表
        include_thoughts: bool = False  # 是否包含思考过程
    ) -> Union[str, Any]:
        """
        统一的聊天接口（使用 Gemini 3 Pro 原生 SDK）

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数（Gemini 3 推荐使用默认值 1.0）
            max_tokens: 最大 token 数
            reasoning_effort: 已弃用，使用 thinking_level
            timeout: 超时时间（秒）
            stream: 是否使用流式传输
            thinking_level: 思考等级 ("low", "high")
            files: PDF 文件路径列表（用于多模态输入）
            include_thoughts: 是否包含思考过程（仅在 stream=True 时有效）

        Returns:
            str 或 Generator: LLM 的回复
        """
        try:
            # 转换 messages 为 Gemini 格式
            contents = self._convert_messages_to_gemini_contents(messages, files)

            # 构建配置
            config = self._build_generation_config(
                temperature=temperature,
                max_tokens=max_tokens,
                thinking_level=thinking_level,
                include_thoughts=include_thoughts
            )

            logger.info(f"🚀 调用 Gemini 3 Pro: model={self.model}, thinking_level={thinking_level}, include_thoughts={include_thoughts}")

            if stream:
                # 流式传输模式
                return self._chat_stream(contents, config, include_thoughts)
            else:
                # 非流式模式
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config
                )
                
                # 提取文本内容
                text = response.text
                logger.info(f"✅ Gemini 响应成功: {len(text)} 字符")
                
                # 记录调用信息
                self._record_last_call(messages, text, temperature, max_tokens, thinking_level)
                
                return text
                
        except Exception as e:
            logger.error(f"❌ Gemini API 调用失败: {e}")
            raise
    
    def _convert_messages_to_gemini_contents(
        self,
        messages: List[Dict[str, Any]],
        files: Optional[List[str]] = None
    ) -> List[Any]:
        """将 OpenAI 格式的 messages 转换为 Gemini 的 contents 格式"""
        contents = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # 跳过 system 消息
            if role == "system":
                continue
            
            # 转换 role
            gemini_role = "model" if role == "assistant" else "user"
            
            # 构建 parts
            parts = []
            
            if isinstance(content, str):
                parts.append(self.types.Part(text=content))
            
            # 添加 PDF 文件
            if files and gemini_role == "user" and not contents:
                for file_path in files:
                    parts.append(self._upload_file(file_path))
            
            if parts:
                contents.append(self.types.Content(role=gemini_role, parts=parts))

        return contents

    def _upload_file(self, file_path: str) -> Any:
        """
        上传文件到 Gemini API（使用 File API）

        Args:
            file_path: 文件路径

        Returns:
            Gemini Part 对象
        """
        try:
            file_path = Path(file_path)

            # 读取文件
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # 确定 MIME 类型
            mime_type = self._get_mime_type(file_path)

            # 使用 inline_data 直接传递文件内容
            import base64
            base64_data = base64.b64encode(file_data).decode('utf-8')

            logger.info(f"📄 上传文件: {file_path.name}, MIME: {mime_type}, 大小: {len(file_data)} bytes")

            return self.types.Part(
                inline_data=self.types.Blob(
                    mime_type=mime_type,
                    data=base64_data
                )
            )

        except Exception as e:
            logger.error(f"❌ 文件上传失败: {file_path}, 错误: {e}")
            raise

    def _get_mime_type(self, file_path: Path) -> str:
        """获取文件的 MIME 类型"""
        suffix = file_path.suffix.lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(suffix, 'application/octet-stream')

    def _build_generation_config(
        self,
        temperature: float,
        max_tokens: Optional[int],
        thinking_level: str,
        include_thoughts: bool = False
    ) -> Any:
        """构建 Gemini 生成配置"""
        config_dict = {
            "temperature": temperature,
        }

        is_flash_model = "flash" in (self.model or "").lower()
        if thinking_level and not is_flash_model:
            config_dict["thinking_config"] = self.types.ThinkingConfig(
                thinking_level=thinking_level,
                include_thoughts=include_thoughts  # 是否包含思考过程
            )
        elif is_flash_model and thinking_level:
            logger.debug(f"Model {self.model} 不支持 thinking_level，已跳过思考配置")

        if max_tokens is not None:
            config_dict["max_output_tokens"] = max_tokens

        return self.types.GenerateContentConfig(**config_dict)

    def _chat_stream(self, contents: List[Any], config: Any, include_thoughts: bool = False) -> Any:
        """
        流式传输模式

        Yields:
            Dict: {"type": "thought" | "text", "content": str}
        """
        try:
            response = self.client.models.generate_content_stream(
                model=self.model,
                contents=contents,
                config=config
            )

            for chunk in response:
                # 检查是否有思考内容（Gemini 3 Pro 特性）
                if include_thoughts and hasattr(chunk, 'candidates') and chunk.candidates:
                    candidate = chunk.candidates[0]
                    if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                        for part in candidate.content.parts:
                            # 思考内容
                            if hasattr(part, 'thought') and part.thought:
                                yield {
                                    "type": "thought",
                                    "content": str(part.thought)
                                }
                            # 普通文本内容
                            elif hasattr(part, 'text') and part.text:
                                yield {
                                    "type": "text",
                                    "content": part.text
                                }
                # 兼容旧版本：直接返回文本
                elif hasattr(chunk, 'text') and chunk.text:
                    yield {
                        "type": "text",
                        "content": chunk.text
                    }

        except Exception as e:
            logger.error(f"❌ Gemini 流式 API 调用失败: {e}")
            raise

    def _record_last_call(
        self,
        messages: List[Dict[str, Any]],
        response: str,
        temperature: float,
        max_tokens: Optional[int],
        thinking_level: str
    ):
        """记录最近一次调用信息"""
        try:
            self.last_call = {
                "provider": "gemini",
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "thinking_level": thinking_level,
                "message_count": len(messages),
                "response_preview": response[:1000] if response else None,
                "timestamp": datetime.now().isoformat()
            }
        except Exception:
            self.last_call = None


def get_llm_client(provider=None, api_key=None, model=None):
    """获取 LLM 客户端实例"""
    return LLMClient(provider=provider, api_key=api_key, model=model)


# 测试代码
if __name__ == '__main__':
    print("=" * 60)
    print("🧪 测试 Gemini 3 Pro Client")
    print("=" * 60)

    client = get_llm_client()

    messages = [
        {"role": "user", "content": "请用一句话介绍 Python 编程语言。"}
    ]

    try:
        response = client.chat(messages)
        print(f"\nGemini 回复:\n{response}\n")
        print("✅ 测试成功！")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
