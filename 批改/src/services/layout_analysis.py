"""布局分析服务 - 使用 Gemini 2.5 Flash Lite 进行页面分割"""

import base64
import json
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from ..models.region import BoundingBox, QuestionRegion, SegmentationResult
from ..utils.coordinates import normalize_coordinates


class LayoutAnalysisService:
    """布局分析服务，使用 Gemini 2.5 Flash Lite 识别试卷中的题目边界"""
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        """
        初始化布局分析服务
        
        Args:
            api_key: Google AI API 密钥
            model_name: 使用的模型名称，默认为 gemini-2.0-flash-exp
        """
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.1
        )
        self.model_name = model_name
        
    async def segment_document(
        self, 
        image_data: bytes, 
        submission_id: str,
        page_index: int = 0
    ) -> SegmentationResult:
        """
        识别试卷图像中的题目边界
        
        Args:
            image_data: 图像数据（字节）
            submission_id: 提交 ID
            page_index: 页面索引
            
        Returns:
            SegmentationResult: 包含识别的题目区域列表
            
        Raises:
            ValueError: 当模型未能识别任何题目区域时
        """
        # 将图像转换为 base64
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        # 构建提示词，要求模型返回结构化的题目边界框
        prompt = """请分析这张试卷图像，识别出所有题目的边界框。

对于每道题目，返回以下信息：
- question_id: 题目编号（如 "q1", "q2" 等）
- bounding_box: 边界框坐标，格式为 [ymin, xmin, ymax, xmax]，使用归一化坐标（0-1000 比例）

请以 JSON 格式返回结果，格式如下：
{
    "regions": [
        {
            "question_id": "q1",
            "bounding_box": [ymin, xmin, ymax, xmax]
        }
    ]
}

如果无法识别任何题目区域，请返回空的 regions 列表。
按照题目在页面上的顺序（从上到下）返回结果。"""

        # 构建消息
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{image_b64}"
                }
            ]
        )
        
        # 调用 LLM
        response = await self.llm.ainvoke([message])
        
        # 解析响应
        result_text = response.content
        # 尝试从响应中提取 JSON
        if "```json" in result_text:
            # 提取 JSON 代码块
            json_start = result_text.find("```json") + 7
            json_end = result_text.find("```", json_start)
            result_text = result_text[json_start:json_end].strip()
        
        result_data = json.loads(result_text)
        
        regions_data = result_data.get("regions", [])
        
        # 如果未识别到任何区域，标记为需要人工审核
        if not regions_data:
            raise ValueError(
                f"未能识别页面 {page_index} 中的任何题目区域，需要人工审核"
            )
        
        # 获取图像尺寸（用于坐标转换）
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_data))
        img_width, img_height = img.size
        
        # 转换为 QuestionRegion 对象
        regions: List[QuestionRegion] = []
        for region_data in regions_data:
            question_id = region_data["question_id"]
            box_1000 = region_data["bounding_box"]
            
            # 将归一化坐标转换为像素坐标
            bounding_box = normalize_coordinates(
                box_1000=box_1000,
                img_width=img_width,
                img_height=img_height
            )
            
            regions.append(
                QuestionRegion(
                    question_id=question_id,
                    page_index=page_index,
                    bounding_box=bounding_box,
                    image_data=None  # 可选：后续可以裁剪图像
                )
            )
        
        return SegmentationResult(
            submission_id=submission_id,
            total_pages=1,  # 单页处理
            regions=regions
        )
