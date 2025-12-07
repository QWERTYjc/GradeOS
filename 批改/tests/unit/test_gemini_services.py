"""Gemini 服务单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import base64
import json

from src.services.layout_analysis import LayoutAnalysisService
from src.services.gemini_reasoning import GeminiReasoningClient
from src.models.region import BoundingBox, QuestionRegion, SegmentationResult


class TestLayoutAnalysisService:
    """布局分析服务测试"""
    
    @pytest.fixture
    def service(self):
        """创建测试服务实例"""
        return LayoutAnalysisService(api_key="test_api_key")
    
    @pytest.fixture
    def mock_image_data(self):
        """创建模拟图像数据"""
        # 创建一个简单的 1x1 像素 JPEG 图像
        from PIL import Image
        import io
        img = Image.new('RGB', (1920, 1080), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        return img_bytes.getvalue()
    
    @patch('src.services.layout_analysis.ChatGoogleGenerativeAI')
    async def test_segment_document_success(self, mock_llm_class, service, mock_image_data):
        """测试成功的文档分割"""
        # 模拟 API 响应
        mock_response = Mock()
        mock_response.content = json.dumps({
            "regions": [
                {
                    "question_id": "q1",
                    "bounding_box": [100, 200, 500, 800]
                },
                {
                    "question_id": "q2",
                    "bounding_box": [600, 200, 900, 800]
                }
            ]
        })
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_class.return_value = mock_llm
        
        # 重新创建服务以使用模拟的 LLM
        service = LayoutAnalysisService(api_key="test_api_key")
        
        # 调用方法
        result = await service.segment_document(
            image_data=mock_image_data,
            submission_id="test_sub_001",
            page_index=0
        )
        
        # 验证结果
        assert isinstance(result, SegmentationResult)
        assert result.submission_id == "test_sub_001"
        assert result.total_pages == 1
        assert len(result.regions) == 2
        assert result.regions[0].question_id == "q1"
        assert result.regions[1].question_id == "q2"
    
    @patch('src.services.layout_analysis.ChatGoogleGenerativeAI')
    async def test_segment_document_no_regions(self, mock_llm_class, service, mock_image_data):
        """测试未识别到区域的情况"""
        # 模拟 API 响应（空区域）
        mock_response = Mock()
        mock_response.content = json.dumps({"regions": []})
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_class.return_value = mock_llm
        
        # 重新创建服务以使用模拟的 LLM
        service = LayoutAnalysisService(api_key="test_api_key")
        
        # 调用方法，应该抛出 ValueError
        with pytest.raises(ValueError, match="未能识别页面.*需要人工审核"):
            await service.segment_document(
                image_data=mock_image_data,
                submission_id="test_sub_001",
                page_index=0
            )


class TestGeminiReasoningClient:
    """Gemini 推理客户端测试"""
    
    @pytest.fixture
    def client(self):
        """创建测试客户端实例"""
        return GeminiReasoningClient(api_key="test_api_key")
    
    @pytest.fixture
    def sample_image_b64(self):
        """创建示例 base64 图像"""
        from PIL import Image
        import io
        img = Image.new('RGB', (100, 100), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        return base64.b64encode(img_bytes.getvalue()).decode('utf-8')
    
    @patch('src.services.gemini_reasoning.ChatGoogleGenerativeAI')
    async def test_vision_extraction(self, mock_llm_class, client, sample_image_b64):
        """测试视觉提取"""
        # 模拟 API 响应
        mock_response = Mock()
        mock_response.content = "学生使用了正确的公式，但在计算过程中出现了错误..."
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_class.return_value = mock_llm
        
        # 重新创建客户端以使用模拟的 LLM
        client = GeminiReasoningClient(api_key="test_api_key")
        
        # 调用方法
        result = await client.vision_extraction(
            question_image_b64=sample_image_b64,
            rubric="1. 正确使用公式 (5分)\n2. 计算正确 (5分)",
            standard_answer="答案：42"
        )
        
        # 验证结果
        assert isinstance(result, str)
        assert len(result) > 0
    
    @patch('src.services.gemini_reasoning.ChatGoogleGenerativeAI')
    async def test_rubric_mapping(self, mock_llm_class, client):
        """测试评分映射"""
        # 模拟 API 响应
        mock_response = Mock()
        mock_response.content = json.dumps({
            "rubric_mapping": [
                {
                    "rubric_point": "正确使用公式",
                    "evidence": "学生在第一行写出了正确的公式",
                    "score_awarded": 5.0,
                    "max_score": 5.0
                },
                {
                    "rubric_point": "计算正确",
                    "evidence": "计算过程有误",
                    "score_awarded": 2.0,
                    "max_score": 5.0
                }
            ],
            "initial_score": 7.0,
            "reasoning": "公式正确但计算有误"
        })
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_class.return_value = mock_llm
        
        # 重新创建客户端以使用模拟的 LLM
        client = GeminiReasoningClient(api_key="test_api_key")
        
        # 调用方法
        result = await client.rubric_mapping(
            vision_analysis="学生使用了正确的公式...",
            rubric="1. 正确使用公式 (5分)\n2. 计算正确 (5分)",
            max_score=10.0
        )
        
        # 验证结果
        assert "rubric_mapping" in result
        assert "initial_score" in result
        assert len(result["rubric_mapping"]) == 2
        assert result["initial_score"] == 7.0
    
    @patch('src.services.gemini_reasoning.ChatGoogleGenerativeAI')
    async def test_critique(self, mock_llm_class, client):
        """测试自我反思"""
        # 模拟 API 响应
        mock_response = Mock()
        mock_response.content = json.dumps({
            "critique_feedback": "评分过于严格，学生的计算方法是正确的",
            "needs_revision": True,
            "confidence": 0.65
        })
        
        mock_llm = Mock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_class.return_value = mock_llm
        
        # 重新创建客户端以使用模拟的 LLM
        client = GeminiReasoningClient(api_key="test_api_key")
        
        # 调用方法
        result = await client.critique(
            vision_analysis="学生使用了正确的公式...",
            rubric="1. 正确使用公式 (5分)\n2. 计算正确 (5分)",
            rubric_mapping=[
                {
                    "rubric_point": "正确使用公式",
                    "evidence": "找到公式",
                    "score_awarded": 5.0,
                    "max_score": 5.0
                }
            ],
            initial_score=7.0,
            max_score=10.0
        )
        
        # 验证结果
        assert "critique_feedback" in result
        assert "needs_revision" in result
        assert "confidence" in result
        assert result["needs_revision"] is True
        assert 0.0 <= result["confidence"] <= 1.0
