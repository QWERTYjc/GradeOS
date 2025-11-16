"""
Textin API客户端封装
实现HTTP请求、认证、错误处理和重试机制
"""
import os
import time
import base64
import logging
from typing import Dict, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import APIParameters, OptimizationMetadata

logger = logging.getLogger(__name__)


class TextinAPIError(Exception):
    """Textin API异常"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Textin API Error {code}: {message}")


class TextinClient:
    """
    Textin API客户端
    封装文档图像切边增强矫正API调用
    """
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        secret_code: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 2
    ):
        """
        初始化客户端
        
        Args:
            app_id: Textin应用ID（默认从环境变量读取）
            secret_code: Textin密钥（默认从环境变量读取）
            api_url: API地址（默认从环境变量读取）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.app_id = app_id or os.getenv('TEXTIN_APP_ID', '')
        self.secret_code = secret_code or os.getenv('TEXTIN_SECRET_CODE', '')
        self.api_url = api_url or os.getenv(
            'TEXTIN_API_URL',
            'https://api.textin.com/ai/service/v1/crop_enhance_image'
        )
        self.timeout = timeout
        self.max_retries = max_retries
        
        # 验证配置
        if not self.app_id or not self.secret_code:
            raise ValueError("Textin API凭证未配置，请设置TEXTIN_APP_ID和TEXTIN_SECRET_CODE环境变量")
        
        # 创建session并配置重试策略
        self.session = self._create_session()
        
        logger.info(f"TextinClient初始化成功，API地址: {self.api_url}")
    
    def _create_session(self) -> requests.Session:
        """创建配置了重试策略的Session"""
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,  # 指数退避：1秒、2秒、4秒...
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的HTTP状态码
            allowed_methods=["POST"]  # 允许重试POST请求
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            'x-ti-app-id': self.app_id,
            'x-ti-secret-code': self.secret_code,
            'Content-Type': 'application/octet-stream'
        }
    
    def _build_url(self, params: APIParameters) -> str:
        """构建请求URL"""
        query_string = params.to_query_string()
        return f"{self.api_url}?{query_string}"
    
    def _read_image_binary(self, image_path: str) -> bytes:
        """读取图片二进制数据"""
        try:
            with open(image_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取图片失败: {image_path}, 错误: {e}")
            raise
    
    def _parse_response(self, response_data: Dict) -> Tuple[bytes, OptimizationMetadata]:
        """
        解析API响应
        
        Args:
            response_data: API响应JSON
            
        Returns:
            (优化后的图片二进制, 元数据)
        """
        code = response_data.get('code', -1)
        message = response_data.get('message', '未知错误')
        
        logger.info(f"API响应: code={code}, message={message}")
        
        # Textin API返回200表示成功
        if code != 200:
            logger.error(f"API返回错误: code={code}, message={message}")
            raise TextinAPIError(code, message)
        
        result = response_data.get('result', {})
        
        # 解析图片列表
        image_list = result.get('image_list', [])
        if not image_list:
            logger.error(f"API响应中无图片数据，完整响应: {response_data}")
            raise TextinAPIError(-1, "API未返回优化图片")
        
        # 获取第一张图片（可能是字典对象）
        first_image = image_list[0]
        
        # 如果是字典，提取image字段
        if isinstance(first_image, dict):
            image_base64 = first_image.get('image', '')
            # 从字典中获取详细元数据
            metadata = OptimizationMetadata(
                origin_width=result.get('origin_w', first_image.get('origin_width', 0)),
                origin_height=result.get('origin_h', first_image.get('origin_height', 0)),
                cropped_width=first_image.get('cropped_width', 0),
                cropped_height=first_image.get('cropped_height', 0),
                position=first_image.get('position', []),
                angle=first_image.get('angle', 0),
                duration=result.get('duration', 0.0)
            )
        else:
            # 直接是Base64字符串
            image_base64 = first_image
            metadata = OptimizationMetadata(
                origin_width=result.get('origin_w', 0),
                origin_height=result.get('origin_h', 0),
                cropped_width=result.get('cropped_w', 0),
                cropped_height=result.get('cropped_h', 0),
                position=result.get('position', []),
                angle=result.get('angle', 0),
                duration=result.get('duration', 0.0)
            )
        
        if not image_base64:
            raise TextinAPIError(-1, "图片数据为空")
        
        # 解码Base64
        image_binary = base64.b64decode(image_base64)
        
        logger.info(f"解析成功，图片大小: {len(image_binary)} bytes")
        
        return image_binary, metadata
    
    def optimize_image(
        self,
        image_path: str,
        params: Optional[APIParameters] = None
    ) -> Tuple[bytes, OptimizationMetadata]:
        """
        优化单张图片
        
        Args:
            image_path: 图片路径
            params: API参数（默认使用智能模式）
            
        Returns:
            (优化后的图片二进制, 元数据)
            
        Raises:
            TextinAPIError: API调用失败
            Exception: 其他错误
        """
        if params is None:
            params = APIParameters()
        
        logger.info(f"开始优化图片: {image_path}, 参数: {params.to_dict()}")
        
        start_time = time.time()
        
        try:
            # 读取图片
            image_binary = self._read_image_binary(image_path)
            
            # 构建请求
            url = self._build_url(params)
            headers = self._build_headers()
            
            # 发送请求
            logger.debug(f"发送API请求: {url}")
            response = self.session.post(
                url,
                headers=headers,
                data=image_binary,
                timeout=self.timeout
            )
            
            # 检查HTTP状态
            response.raise_for_status()
            
            # 解析响应
            response_data = response.json()
            image_binary, metadata = self._parse_response(response_data)
            
            elapsed_time = (time.time() - start_time) * 1000
            logger.info(
                f"图片优化成功: {image_path}, "
                f"尺寸变化: {metadata.origin_width}x{metadata.origin_height} → "
                f"{metadata.cropped_width}x{metadata.cropped_height}, "
                f"耗时: {elapsed_time:.0f}ms"
            )
            
            return image_binary, metadata
            
        except requests.exceptions.Timeout:
            logger.error(f"API请求超时: {image_path}, 超时时间: {self.timeout}秒")
            raise TextinAPIError(-1, f"请求超时（{self.timeout}秒）")
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"API连接失败: {e}")
            raise TextinAPIError(-1, "网络连接失败，请检查网络")
        
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            logger.error(f"HTTP错误: {status_code}, {e}")
            
            if status_code == 401:
                raise TextinAPIError(401, "认证失败，请检查API凭证")
            elif status_code == 429:
                raise TextinAPIError(429, "API调用限流，请稍后重试")
            else:
                raise TextinAPIError(status_code, f"HTTP错误: {status_code}")
        
        except TextinAPIError:
            raise
        
        except Exception as e:
            logger.error(f"优化图片失败: {image_path}, 错误: {e}", exc_info=True)
            raise
    
    def check_api_status(self) -> bool:
        """
        检查API可用性
        
        Returns:
            API是否可用
        """
        try:
            # 使用一个小的测试请求
            headers = self._build_headers()
            response = self.session.get(
                self.api_url,
                headers=headers,
                timeout=5
            )
            
            # 任何非5xx响应都认为API可用
            return response.status_code < 500
            
        except Exception as e:
            logger.warning(f"API状态检查失败: {e}")
            return False
    
    def close(self):
        """关闭Session"""
        if self.session:
            self.session.close()
            logger.debug("TextinClient Session已关闭")
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
