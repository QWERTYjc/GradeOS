"""统一 LLM 客户端
提供统一的 LLM 调用接口，支持：
- OpenRouter API（可混合各家模型）
- 直连 Google Gemini API
- 流式输出
- 视觉模型支持
"""
import logging
import base64
from typing import List, Dict, Any, Optional, AsyncIterator, Union
from dataclasses import dataclass
import httpx
from src.config.llm import get_llm_config, LLMConfig, LLMProvider
logger = logging.getLogger(__name__)
@dataclass
class LLMMessage:
    """LLM 消息"""
    role: str  # "system", "user", "assistant"
    content: Union[str, List[Dict[str, Any]]]  # 文本或多模态内容
@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    usage: Dict[str, int] = None
    finish_reason: str = None
class UnifiedLLMClient:
    """统一 LLM 客户端"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or get_llm_config()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client
    
    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self.config.get_headers())
        return headers
    
    def _format_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """格式化消息为 API 格式"""
        formatted = []
        for msg in messages:
            if isinstance(msg.content, str):
                formatted.append({
                    "role": msg.role,
                    "content": msg.content
                })
                continue
            content = msg.content
            if self.config.provider == LLMProvider.OPENROUTER and isinstance(content, list):
                normalized = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        image_url = item.get("image_url")
                        if isinstance(image_url, str):
                            normalized.append({
                                **item,
                                "image_url": {"url": image_url}
                            })
                            continue
                    normalized.append(item)
                content = normalized
            formatted.append({
                "role": msg.role,
                "content": content
            })
        return formatted
    
    @staticmethod
    def create_image_content(image_bytes: bytes, media_type: str = "image/jpeg") -> Dict[str, Any]:
        """创建图像内容块"""
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{base64_image}"
            }
        }
    
    @staticmethod
    def create_text_content(text: str) -> Dict[str, Any]:
        """创建文本内容块"""
        return {
            "type": "text",
            "text": text
        }
    
    async def invoke(
        self,
        messages: List[LLMMessage],
        purpose: str = "text",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """
        调用 LLM
        
        Args:
            messages: 消息列表
            purpose: 用途（vision, text, summary, rubric）
            temperature: 温度
            max_tokens: 最大 token 数
            
        Returns:
            LLMResponse: LLM 响应
        """
        model = self.config.get_model(purpose)
        client = await self._get_client()
        
        payload = {
            "model": model,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        logger.info(f"[LLM] 调用模型: {model}, 用途: {purpose}, 消息数: {len(messages)}")
        
        try:
            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {}) or {}
            header_usage = {}
            header_key = response.headers.get("x-openrouter-usage") or response.headers.get("x-usage")
            if header_key:
                try:
                    import json
                    header_usage = json.loads(header_key)
                except Exception:
                    header_usage = {}
            if header_usage:
                usage = {**usage, **header_usage}
            logger.info(
                f"[LLM] 响应成功: {len(content)} chars, tokens: {usage}"
            )
            if self.config.provider == LLMProvider.OPENROUTER:
                logger.info(f"[LLM] OpenRouter token usage: {usage}")
            
            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                finish_reason=choice.get("finish_reason")
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"[LLM] HTTP 错误: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.HTTPStatusError as e:
            try:
                body = await e.response.aread()
                text = body.decode("utf-8", errors="replace")
            except Exception:
                text = "<unreadable response>"
            logger.error(f"[LLM] HTTP error: {e.response.status_code} - {text}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[LLM] HTTP error: {e.response.status_code} - {e.response.text} "
                f"(model={model}, purpose={purpose}, images={image_count})"
            )
            raise
        except Exception as e:
            logger.error(f"[LLM] stream failed: {e}")
            raise
    
    async def stream(
        self,
        messages: List[LLMMessage],
        purpose: str = "text",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        流式调用 LLM
        
        Args:
            messages: 消息列表
            purpose: 用途
            temperature: 温度
            max_tokens: 最大 token 数
            
        Yields:
            str: 内容块
        """
        model = self.config.get_model(purpose)
        client = await self._get_client()
        
        payload = {
            "model": model,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            **kwargs
        }
        if self.config.provider == LLMProvider.OPENROUTER:
            payload["stream_options"] = {"include_usage": True}

        image_count = 0
        for msg in payload["messages"]:
            content = msg.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image_url":
                        image_count += 1

        logger.info(
            f"[LLM] stream call: {model}, purpose={purpose}, images={image_count}, messages={len(payload['messages'])}"
        )

        try:
            usage_summary: Dict[str, int] = {}
            async with client.stream(
                "POST",
                f"{self.config.base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            import json
                            data = json.loads(data_str)
                            if data.get("usage"):
                                usage_summary = data.get("usage") or usage_summary
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except Exception:
                            continue
            if usage_summary and self.config.provider == LLMProvider.OPENROUTER:
                logger.info(f"[LLM] OpenRouter token usage (stream): {usage_summary}")
        except httpx.HTTPStatusError as e:
            logger.error(f"[LLM] HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[LLM] stream failed: {e}")
            raise
    
    async def invoke_with_images(
        self,
        prompt: str,
        images: List[bytes],
        purpose: str = "vision",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """
        调用视觉模型
        
        Args:
            prompt: 文本提示
            images: 图像字节列表
            purpose: 用途
            system_prompt: 系统提示
            temperature: 温度
            max_tokens: 最大 token 数
            
        Returns:
            LLMResponse: LLM 响应
        """
        # 构建多模态消息
        content = []
        
        # 添加图像
        for img in images:
            content.append(self.create_image_content(img))
        
        # 添加文本
        content.append(self.create_text_content(prompt))
        
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=content))
        
        return await self.invoke(
            messages=messages,
            purpose=purpose,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
# 全局客户端实例
_llm_client: Optional[UnifiedLLMClient] = None
def get_llm_client() -> UnifiedLLMClient:
    """获取全局 LLM 客户端"""
    global _llm_client
    if _llm_client is None:
        _llm_client = UnifiedLLMClient()
    return _llm_client
async def close_llm_client():
    """关闭全局 LLM 客户端"""
    global _llm_client
    if _llm_client:
        await _llm_client.close()
        _llm_client = None
