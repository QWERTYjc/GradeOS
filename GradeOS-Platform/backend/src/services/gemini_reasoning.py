"""Gemini 深度推理客户端 - 使用 Gemini 进行批改推理

本模块实现了批改工作流的核心推理能力，集成了：
- RubricRegistry: 动态获取评分标准
- GradingSkills: Agent 技能模块
- 得分点逐一核对逻辑
- 另类解法支持
- 指数退避重试机制 (Requirement 9.1)

Requirements: 1.1, 1.2, 1.3, 9.1
"""

import base64
import json
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from ..models.grading import RubricMappingItem
from ..models.grading_models import (
    QuestionRubric,
    QuestionResult,
    ScoringPoint,
    ScoringPointResult,
    PageGradingResult,
    StudentInfo,
)
from ..config.models import get_default_model
from ..utils.error_handling import with_retry, get_error_manager

if TYPE_CHECKING:
    from ..services.rubric_registry import RubricRegistry
    from ..skills.grading_skills import GradingSkills


logger = logging.getLogger(__name__)


class GeminiReasoningClient:
    """
    Gemini 深度推理客户端，用于批改智能体的各个推理节点
    
    集成了 RubricRegistry 和 GradingSkills，支持：
    - 动态评分标准获取 (Requirement 1.1)
    - 得分点逐一核对 (Requirement 1.2)
    - 另类解法支持 (Requirement 1.3)
    
    Requirements: 1.1, 1.2, 1.3
    """
    
    # 类常量：避免魔法数字
    MAX_QUESTIONS_IN_PROMPT = 20  # 提示词中最多显示的题目数
    MAX_CRITERIA_PER_QUESTION = 3  # 每道题最多显示的评分要点数
    
    def __init__(
        self, 
        api_key: str, 
        model_name: Optional[str] = None,
        rubric_registry: Optional["RubricRegistry"] = None,
        grading_skills: Optional["GradingSkills"] = None,
    ):
        """
        初始化 Gemini 推理客户端
        
        Args:
            api_key: Google AI API 密钥
            model_name: 使用的模型名称，默认使用全局配置
            rubric_registry: 评分标准注册中心（可选）
            grading_skills: Agent Skills 模块（可选）
        """
        if model_name is None:
            model_name = get_default_model()
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2
        )
        self.model_name = model_name
        self.temperature = 0.2  # 低温度以保持一致性
        
        # 集成 RubricRegistry 和 GradingSkills (Requirement 1.1)
        self._rubric_registry = rubric_registry
        self._grading_skills = grading_skills
    
    @property
    def rubric_registry(self) -> Optional["RubricRegistry"]:
        """获取评分标准注册中心"""
        return self._rubric_registry
    
    @rubric_registry.setter
    def rubric_registry(self, registry: "RubricRegistry") -> None:
        """设置评分标准注册中心"""
        self._rubric_registry = registry
        # 同步更新 GradingSkills 的 registry
        if self._grading_skills:
            self._grading_skills.rubric_registry = registry
    
    @property
    def grading_skills(self) -> Optional["GradingSkills"]:
        """获取 Agent Skills 模块"""
        return self._grading_skills
    
    @grading_skills.setter
    def grading_skills(self, skills: "GradingSkills") -> None:
        """设置 Agent Skills 模块"""
        self._grading_skills = skills
        # 设置 LLM 客户端
        if skills:
            skills.llm_client = self.llm
    
    def _extract_text_from_response(self, content: Any) -> str:
        """
        从响应中提取文本内容
        
        Args:
            content: 响应内容（可能是字符串或列表）
            
        Returns:
            str: 提取的文本
        """
        if isinstance(content, list):
            # Gemini 3.0 返回列表格式
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    text_parts.append(item.get('text', ''))
                else:
                    text_parts.append(str(item))
            return '\n'.join(text_parts)
        return str(content)
    
    def _extract_json_from_text(self, text: str) -> str:
        """
        从文本中提取 JSON 部分
        
        Args:
            text: 包含 JSON 的文本
            
        Returns:
            str: 提取的 JSON 字符串
        """
        if "```json" in text:
            json_start = text.find("```json") + 7
            json_end = text.find("```", json_start)
            return text[json_start:json_end].strip()
        elif "```" in text:
            json_start = text.find("```") + 3
            json_end = text.find("```", json_start)
            return text[json_start:json_end].strip()
        return text
    
    @with_retry(max_retries=3, initial_delay=1.0, max_delay=60.0)
    async def _call_vision_api(
        self,
        image_b64: str,
        prompt: str
    ) -> str:
        """
        调用视觉 API (带指数退避重试)
        
        API 调用失败时使用指数退避策略重试最多3次。
        
        Args:
            image_b64: Base64 编码的图像
            prompt: 提示词
            
        Returns:
            str: LLM 响应文本
            
        验证：需求 9.1
        """
        try:
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": f"data:image/png;base64,{image_b64}"
                    }
                ]
            )
            
            response = await self.llm.ainvoke([message])
            return self._extract_text_from_response(response.content)
        except Exception as e:
            # 记录错误到全局错误管理器
            error_manager = get_error_manager()
            error_manager.add_error(
                exc=e,
                context={
                    "function": "_call_vision_api",
                    "prompt_length": len(prompt),
                    "image_size": len(image_b64),
                }
            )
            raise
    
    @with_retry(max_retries=3, initial_delay=1.0, max_delay=60.0)
    async def _call_text_api(
        self,
        prompt: str
    ) -> str:
        """
        调用纯文本 API (带指数退避重试)
        
        用于处理纯文本输入（如文本文件内容），不包含图像。
        
        Args:
            prompt: 提示词（包含学生答案文本）
            
        Returns:
            str: LLM 响应文本
        """
        try:
            message = HumanMessage(content=prompt)
            response = await self.llm.ainvoke([message])
            return self._extract_text_from_response(response.content)
        except Exception as e:
            error_manager = get_error_manager()
            error_manager.add_error(
                exc=e,
                context={
                    "function": "_call_text_api",
                    "prompt_length": len(prompt),
                }
            )
            raise
    
    def _is_text_content(self, data: bytes) -> bool:
        """
        检测输入是否为纯文本内容
        
        Args:
            data: 输入数据（bytes）
            
        Returns:
            bool: 如果是可解码的 UTF-8 文本返回 True
        """
        try:
            # 尝试解码为 UTF-8 文本
            text = data.decode('utf-8')
            # 检查是否包含常见的文本特征（中文字符、换行符等）
            # 排除二进制文件（如 PNG/PDF 的魔数）
            if data[:4] in [b'\x89PNG', b'%PDF', b'\xff\xd8\xff']:
                return False
            # 如果能成功解码且包含可打印字符，认为是文本
            printable_ratio = sum(1 for c in text if c.isprintable() or c in '\n\r\t') / len(text)
            return printable_ratio > 0.8
        except (UnicodeDecodeError, ZeroDivisionError):
            return False
        
    async def vision_extraction(
        self,
        question_image_b64: str,
        rubric: str,
        standard_answer: Optional[str] = None
    ) -> str:
        """
        视觉提取节点：分析学生答案图像，生成详细的文字描述
        
        Args:
            question_image_b64: Base64 编码的题目图像
            rubric: 评分细则
            standard_answer: 标准答案（可选）
            
        Returns:
            str: 学生解题步骤的详细文字描述
        """
        # 构建提示词
        prompt = f"""请仔细分析这张学生答题图像，提供详细的文字描述。

评分细则：
{rubric}

{f"标准答案：{standard_answer}" if standard_answer else ""}

请描述：
1. 学生写了什么内容（公式、文字、图表等）
2. 学生的解题步骤和思路
3. 学生的计算过程
4. 任何可见的错误或遗漏

请提供详细、客观的描述，不要进行评分，只描述你看到的内容。"""

        # 构建消息
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{question_image_b64}"
                }
            ]
        )
        
        # 调用 LLM
        response = await self.llm.ainvoke([message])
        
        # 提取文本内容
        return self._extract_text_from_response(response.content)
    
    async def rubric_mapping(
        self,
        vision_analysis: str,
        rubric: str,
        max_score: float,
        standard_answer: Optional[str] = None,
        critique_feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        评分映射节点：将评分细则的每个评分点映射到学生答案中的证据
        
        Args:
            vision_analysis: 视觉分析结果
            rubric: 评分细则
            max_score: 满分
            standard_answer: 标准答案（可选）
            critique_feedback: 反思反馈（如果是修正循环）
            
        Returns:
            Dict: 包含 rubric_mapping 和 initial_score
        """
        # 构建提示词
        prompt = f"""基于以下学生答案的视觉分析，请逐条核对评分细则，并给出评分。

视觉分析：
{vision_analysis}

评分细则：
{rubric}

满分：{max_score}

{f"标准答案：{standard_answer}" if standard_answer else ""}

{f"修正反馈：{critique_feedback}" if critique_feedback else ""}

请对每个评分点进行评估，返回 JSON 格式：
{{
    "rubric_mapping": [
        {{
            "rubric_point": "评分点描述",
            "evidence": "在学生答案中找到的证据（如果没有找到，说明'未找到'）",
            "score_awarded": 获得的分数,
            "max_score": 该评分点的满分
        }}
    ],
    "initial_score": 总得分,
    "reasoning": "评分理由"
}}"""

        # 调用 LLM
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        
        # 提取文本内容
        result_text = self._extract_text_from_response(response.content)
        result_text = self._extract_json_from_text(result_text)
        
        result = json.loads(result_text)
        return result
    
    async def critique(
        self,
        vision_analysis: str,
        rubric: str,
        rubric_mapping: List[Dict[str, Any]],
        initial_score: float,
        max_score: float,
        standard_answer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        自我反思节点：审查评分逻辑，识别潜在的评分错误
        
        Args:
            vision_analysis: 视觉分析结果
            rubric: 评分细则
            rubric_mapping: 评分点映射
            initial_score: 初始评分
            max_score: 满分
            standard_answer: 标准答案（可选）
            
        Returns:
            Dict: 包含 critique_feedback 和 needs_revision
        """
        # 构建提示词
        prompt = f"""请审查以下评分结果，识别潜在的评分错误或不一致之处。

视觉分析：
{vision_analysis}

评分细则：
{rubric}

评分映射：
{json.dumps(rubric_mapping, ensure_ascii=False, indent=2)}

初始评分：{initial_score}/{max_score}

{f"标准答案：{standard_answer}" if standard_answer else ""}

请检查：
1. 评分点是否都被正确评估？
2. 证据是否充分支持给出的分数？
3. 是否有遗漏的评分点？
4. 评分是否过于严格或宽松？
5. 总分是否正确计算？

返回 JSON 格式：
{{
    "critique_feedback": "反思反馈（如果没有问题，返回 null）",
    "needs_revision": true/false,
    "confidence": 0.0-1.0 之间的置信度分数
}}"""

        # 调用 LLM
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        
        # 提取文本内容
        result_text = self._extract_text_from_response(response.content)
        result_text = self._extract_json_from_text(result_text)
        
        result = json.loads(result_text)
        return result

    async def analyze_with_vision(
        self,
        images: List[bytes],
        prompt: str
    ) -> Dict[str, Any]:
        """
        通用视觉分析方法：分析多张图像并返回结构化结果
        
        Args:
            images: 图像字节列表
            prompt: 分析提示词
            
        Returns:
            Dict: 包含 response 的结果
        """
        # 构建消息内容
        content = [{"type": "text", "text": prompt}]
        
        # 添加图像
        for img_bytes in images:
            if isinstance(img_bytes, bytes):
                img_b64 = base64.b64encode(img_bytes).decode('utf-8')
            else:
                img_b64 = img_bytes  # 已经是 base64 字符串
            
            content.append({
                "type": "image_url",
                "image_url": f"data:image/png;base64,{img_b64}"
            })
        
        # 调用 LLM
        message = HumanMessage(content=content)
        response = await self.llm.ainvoke([message])
        
        # 提取文本内容
        result_text = self._extract_text_from_response(response.content)
        
        return {"response": result_text}

    def _format_page_index_context(
        self,
        page_context: Optional[Dict[str, Any]]
    ) -> str:
        """格式化索引上下文，用于提示词注入"""
        if not page_context:
            return ""

        student_info = page_context.get("student_info") or {}
        student_parts = []
        if student_info:
            name = student_info.get("name") or "未知"
            student_id = student_info.get("student_id") or "未知"
            class_name = student_info.get("class_name") or "未知"
            confidence = student_info.get("confidence", 0.0)
            student_parts.append(f"姓名={name}")
            student_parts.append(f"学号={student_id}")
            student_parts.append(f"班级={class_name}")
            student_parts.append(f"置信度={confidence}")

        question_numbers = page_context.get("question_numbers") or []
        continuation_of = page_context.get("continuation_of") or "无"
        notes = page_context.get("index_notes") or []

        return (
            "## 索引上下文（优先使用）\n"
            f"- page_index: {page_context.get('page_index')}\n"
            f"- question_numbers: {', '.join(question_numbers) if question_numbers else '无'}\n"
            f"- continuation_of: {continuation_of}\n"
            f"- is_cover_page: {page_context.get('is_cover_page', False)}\n"
            f"- student_key: {page_context.get('student_key', '未知')}\n"
            f"- student_info: {', '.join(student_parts) if student_parts else '无'}\n"
            f"- notes: {', '.join(notes) if notes else '无'}\n"
        )

    # ==================== grade_page 拆分为多个私有方法 ====================
    
    def _build_grading_prompt(
        self,
        rubric: str,
        parsed_rubric: Optional[Dict[str, Any]],
        page_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建评分提示词
        
        Args:
            rubric: 评分细则文本
            parsed_rubric: 解析后的评分标准
            
        Returns:
            str: 完整的评分提示词
        """
        # 优先使用解析后的评分标准上下文
        rubric_info = ""
        
        if parsed_rubric and parsed_rubric.get("rubric_context"):
            # 使用格式化的评分标准上下文
            rubric_info = parsed_rubric["rubric_context"]
        elif parsed_rubric and parsed_rubric.get("questions"):
            # 从题目信息构建评分标准
            questions_info = []
            for q in parsed_rubric.get("questions", [])[:self.MAX_QUESTIONS_IN_PROMPT]:
                q_info = f"第{q.get('id', '?')}题 (满分{q.get('max_score', 0)}分):"
                
                # 添加评分要点
                criteria = q.get("criteria", [])
                scoring_points = q.get("scoring_points", [])
                
                if scoring_points:
                    for sp in scoring_points[:self.MAX_CRITERIA_PER_QUESTION]:
                        q_info += f"\n  - [{sp.get('score', 0)}分] {sp.get('description', '')}"
                elif criteria:
                    for criterion in criteria[:self.MAX_CRITERIA_PER_QUESTION]:
                        q_info += f"\n  - {criterion}"
                
                # 添加标准答案摘要
                if q.get("standard_answer"):
                    answer_preview = q["standard_answer"][:100] + "..." if len(q["standard_answer"]) > 100 else q["standard_answer"]
                    q_info += f"\n  标准答案: {answer_preview}"
                
                questions_info.append(q_info)
            
            rubric_info = f"评分标准（共{parsed_rubric.get('total_questions', 0)}题，总分{parsed_rubric.get('total_score', 0)}分）：\n\n" + "\n\n".join(questions_info)
        elif rubric:
            # 使用原始评分细则
            rubric_info = rubric
        else:
            # 默认评分标准
            rubric_info = "请根据答案的正确性、完整性和清晰度进行评分"

        index_context = self._format_page_index_context(page_context)

        return f"""你是一位专业的阅卷教师，请仔细分析这张学生答题图像并进行精确评分。

## 评分标准
{rubric_info}
{index_context}

## 评分任务

### 第一步：页面类型判断
首先判断这是否是以下类型的页面：
- 空白页（无任何内容）
- 封面页（只有标题、姓名、学号等信息）
- 目录页
- 无学生作答内容的页面

如果是上述类型，直接返回 score=0, max_score=0, is_blank_page=true
如果索引上下文标记 is_cover_page=true，也直接返回空白页结果

### 第二步：题目识别与评分
如果页面包含学生作答内容：
1. 识别页面中出现的所有题目编号（如提供了索引上下文，必须以索引为准）
2. 对每道题逐一评分，严格按照评分标准
3. 记录学生答案的关键内容
4. 给出详细的评分说明

### 第三步：学生信息提取
尝试从页面中识别：
- 学生姓名
- 学号
- 班级信息

## 输出格式（JSON）
```json
{{
    "score": 本页总得分,
    "max_score": 本页涉及题目的满分总和,
    "confidence": 评分置信度（0.0-1.0）,
    "is_blank_page": false,
    "question_numbers": ["1", "2", "3"],
    "question_details": [
        {{
            "question_id": "1",
            "score": 8,
            "max_score": 10,
            "student_answer": "学生写了：...",
            "is_correct": false,
            "feedback": "第1步正确得3分，第2步计算错误扣2分..."
        }}
    ],
    "page_summary": "本页包含第1-3题，学生整体表现良好，主要在计算方面有失误",
    "student_info": {{
        "name": "张三",
        "student_id": "2024001"
    }}
}}
```

## 重要评分原则
1. **严格遵循评分标准**：每个得分点必须有明确依据
2. **部分分数**：如果学生答案部分正确，给予相应的部分分数
3. **max_score 计算**：只计算本页实际出现的题目的满分，不是整张试卷的总分
4. **详细反馈**：明确指出正确和错误的部分，给出具体的扣分原因
5. **客观公正**：不因字迹潦草等非内容因素扣分，除非评分标准明确要求
6. **空白页处理**：空白页、封面页、目录页的 score 和 max_score 都为 0"""

    def _parse_grading_response(
        self,
        response_text: str,
        max_score: float
    ) -> Dict[str, Any]:
        """
        解析评分响应
        
        Args:
            response_text: LLM 响应文本
            max_score: 满分
            
        Returns:
            Dict: 解析后的评分结果
        """
        json_text = self._extract_json_from_text(response_text)
        return json.loads(json_text)
    
    def _generate_feedback(self, result: Dict[str, Any]) -> str:
        """
        从评分结果生成综合反馈
        
        Args:
            result: 评分结果字典
            
        Returns:
            str: 综合反馈文本
        """
        feedback_parts = []
        
        if result.get("page_summary"):
            feedback_parts.append(result["page_summary"])
        
        for q in result.get("question_details", []):
            q_feedback = f"第{q.get('question_id', '?')}题: {q.get('score', 0)}/{q.get('max_score', 0)}分"
            if q.get("feedback"):
                q_feedback += f" - {q['feedback']}"
            feedback_parts.append(q_feedback)
        
        return "\n".join(feedback_parts) if feedback_parts else "评分完成"

    def _build_text_grading_prompt(
        self,
        text_content: str,
        rubric: str,
        parsed_rubric: Optional[Dict[str, Any]],
        page_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建纯文本批改的提示词
        
        Args:
            text_content: 学生答案文本内容
            rubric: 评分细则文本
            parsed_rubric: 解析后的评分标准
            
        Returns:
            str: 完整的评分提示词
        """
        # 获取评分标准信息
        rubric_info = ""
        if parsed_rubric and parsed_rubric.get("rubric_context"):
            rubric_info = parsed_rubric["rubric_context"]
        elif rubric:
            rubric_info = rubric
        else:
            rubric_info = "请根据答案的正确性、完整性和清晰度进行评分"
        
        index_context = self._format_page_index_context(page_context)

        return f"""你是一位专业的阅卷教师，请仔细分析以下学生答案文本并进行精确评分。

## 评分标准
{rubric_info}
{index_context}

## 学生答案文本
```
{text_content}
```

## 评分任务

### 第一步：内容判断
首先判断这是否是有效的答题内容：
- 如果是空白或无意义内容，返回 score=0, max_score=0, is_blank_page=true
- 如果索引上下文标记 is_cover_page=true，也按空白页处理

### 第二步：题目识别与评分
如果包含有效答题内容：
1. 识别文本中出现的所有题目编号（如提供了索引上下文，必须以索引为准）
2. 对每道题逐一评分，严格按照评分标准
3. 记录学生答案的关键内容
4. 给出详细的评分说明

### 第三步：学生信息提取
尝试从文本中识别：
- 学生姓名
- 学号
- 班级信息

## 输出格式（JSON）
```json
{{
    "score": 本页总得分,
    "max_score": 本页涉及题目的满分总和,
    "confidence": 评分置信度（0.0-1.0）,
    "is_blank_page": false,
    "question_numbers": ["1", "2", "3"],
    "question_details": [
        {{
            "question_id": "1",
            "score": 8,
            "max_score": 10,
            "student_answer": "学生写了：...",
            "is_correct": false,
            "feedback": "第1步正确得3分，第2步计算错误扣2分..."
        }}
    ],
    "page_summary": "本页包含第1-3题，学生整体表现良好，主要在计算方面有失误",
    "student_info": {{
        "name": "张三",
        "student_id": "2024001"
    }}
}}
```

## 重要评分原则
1. **严格遵循评分标准**：每个得分点必须有明确依据
2. **部分分数**：如果学生答案部分正确，给予相应的部分分数
3. **max_score 计算**：只计算本页实际出现的题目的满分，不是整张试卷的总分
4. **详细反馈**：明确指出正确和错误的部分，给出具体的扣分原因"""

    async def grade_page(
        self,
        image: bytes,
        rubric: str,
        max_score: float = 10.0,
        parsed_rubric: Optional[Dict[str, Any]] = None,
        page_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        批改单页：分析图像或文本并给出详细评分
        
        自动检测输入类型（图像或文本），使用相应的 API 进行批改。
        
        Args:
            image: 图像字节或文本字节
            rubric: 评分细则文本
            max_score: 满分
            parsed_rubric: 解析后的评分标准（包含题目信息）
            
        Returns:
            Dict: 包含详细评分结果
        """
        logger.debug(f"开始批改单页, rubric长度={len(rubric)}")
        
        # 检测输入类型：文本还是图像
        is_text = isinstance(image, bytes) and self._is_text_content(image)
        
        try:
            if is_text:
                # 纯文本输入：使用文本 API
                text_content = image.decode('utf-8')
                logger.info(f"检测到文本输入，长度={len(text_content)}字符，使用文本API批改")
                
                # 构建文本批改提示词
                prompt = self._build_text_grading_prompt(
                    text_content,
                    rubric,
                    parsed_rubric,
                    page_context
                )
                
                # 调用文本 API
                response_text = await self._call_text_api(prompt)
            else:
                # 图像输入：使用视觉 API
                logger.info("检测到图像输入，使用视觉API批改")
                
                # 构建图像批改提示词
                prompt = self._build_grading_prompt(rubric, parsed_rubric, page_context)
                
                # 转换图像为 base64
                if isinstance(image, bytes):
                    img_b64 = base64.b64encode(image).decode('utf-8')
                else:
                    img_b64 = image
                
                # 调用视觉 API
                response_text = await self._call_vision_api(img_b64, prompt)
            
            # 解析响应
            result = self._parse_grading_response(response_text, max_score)
            
            # 生成综合反馈
            result["feedback"] = self._generate_feedback(result)
            
            logger.info(
                f"批改完成: score={result.get('score')}, "
                f"confidence={result.get('confidence')}"
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"评分 JSON 解析失败: {e}")
            return {
                "score": 0.0,
                "max_score": max_score,
                "confidence": 0.0,
                "feedback": f"评分解析失败: {str(e)}",
                "question_numbers": [],
                "question_details": [],
                "student_info": None
            }
        except Exception as e:
            logger.error(f"评分失败: {e}", exc_info=True)
            return {
                "score": 0.0,
                "max_score": max_score,
                "confidence": 0.0,
                "feedback": f"评分失败: {str(e)}",
                "question_numbers": [],
                "question_details": [],
                "student_info": None
            }

    # ==================== 动态评分标准获取与得分点核对 ====================
    
    async def get_rubric_for_question(
        self,
        question_id: str,
    ) -> Optional[QuestionRubric]:
        """
        动态获取指定题目的评分标准 (Requirement 1.1)
        
        从 RubricRegistry 获取指定题目的评分标准，包括得分点、标准答案、另类解法。
        
        Args:
            question_id: 题目编号（如 "1", "7a", "15"）
            
        Returns:
            QuestionRubric: 该题目的完整评分标准，如果未找到返回 None
        """
        if self._rubric_registry is None:
            logger.warning("未设置 RubricRegistry，无法获取评分标准")
            return None
        
        result = self._rubric_registry.get_rubric_for_question(question_id)
        
        if result.is_default:
            logger.warning(
                f"题目 {question_id} 使用默认评分标准，置信度: {result.confidence}"
            )
        
        return result.rubric
    
    def _build_scoring_point_prompt(
        self,
        rubric: QuestionRubric,
        student_answer: str,
    ) -> str:
        """
        构建得分点逐一核对的提示词 (Requirement 1.2)
        
        Args:
            rubric: 评分标准
            student_answer: 学生答案描述
            
        Returns:
            str: 得分点核对提示词
        """
        # 构建得分点列表
        scoring_points_text = ""
        for i, sp in enumerate(rubric.scoring_points, 1):
            required_mark = "【必须】" if sp.is_required else "【可选】"
            scoring_points_text += f"{i}. {required_mark} {sp.description} ({sp.score}分)\n"
        
        # 构建另类解法列表 (Requirement 1.3)
        alternative_text = ""
        if rubric.alternative_solutions:
            alternative_text = "\n## 另类解法（同样有效）\n"
            for i, alt in enumerate(rubric.alternative_solutions, 1):
                alternative_text += f"{i}. {alt.description}\n"
                alternative_text += f"   评分条件: {alt.scoring_conditions}\n"
                alternative_text += f"   最高分: {alt.max_score}分\n"
        
        return f"""请对以下学生答案进行得分点逐一核对评分。

## 题目信息
- 题号: {rubric.question_id}
- 满分: {rubric.max_score}分
- 题目: {rubric.question_text}

## 标准答案
{rubric.standard_answer}

## 得分点列表
{scoring_points_text}
{alternative_text}
## 批改注意事项
{rubric.grading_notes if rubric.grading_notes else "无特殊注意事项"}

## 学生答案
{student_answer}

## 评分任务
请逐一核对每个得分点，判断学生是否获得该得分点的分数。

注意：
1. 如果学生使用了另类解法，只要符合评分条件，同样给分
2. 部分正确的得分点可以给部分分数
3. 必须为每个得分点提供证据说明

## 输出格式（JSON）
```json
{{
    "question_id": "{rubric.question_id}",
    "total_score": 学生总得分,
    "max_score": {rubric.max_score},
    "confidence": 评分置信度（0.0-1.0）,
    "used_alternative_solution": false,
    "alternative_solution_index": null,
    "scoring_point_results": [
        {{
            "point_index": 1,
            "description": "得分点描述",
            "max_score": 该得分点满分,
            "awarded": 获得的分数,
            "evidence": "在学生答案中找到的证据或未找到的说明"
        }}
    ],
    "feedback": "综合评价和改进建议"
}}
```"""

    async def grade_question_with_scoring_points(
        self,
        question_id: str,
        student_answer: str,
        image: Optional[bytes] = None,
    ) -> QuestionResult:
        """
        使用得分点逐一核对方式评分单道题目 (Requirement 1.2)
        
        动态获取评分标准，逐一核对每个得分点，支持另类解法。
        
        Args:
            question_id: 题目编号
            student_answer: 学生答案描述（从视觉分析获得）
            image: 可选的题目图像（用于视觉验证）
            
        Returns:
            QuestionResult: 包含得分点明细的评分结果
        """
        # 1. 动态获取评分标准 (Requirement 1.1)
        rubric = await self.get_rubric_for_question(question_id)
        
        if rubric is None:
            logger.error(f"无法获取题目 {question_id} 的评分标准")
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=0.0,
                confidence=0.0,
                feedback="无法获取评分标准",
                scoring_point_results=[],
                page_indices=[],
                is_cross_page=False,
                student_answer=student_answer,
            )
        
        # 2. 构建得分点核对提示词
        prompt = self._build_scoring_point_prompt(rubric, student_answer)
        
        # 3. 调用 LLM 进行评分
        try:
            if image:
                # 如果有图像，使用视觉 API
                img_b64 = base64.b64encode(image).decode('utf-8') if isinstance(image, bytes) else image
                response_text = await self._call_vision_api(img_b64, prompt)
            else:
                # 纯文本评分
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                response_text = self._extract_text_from_response(response.content)
            
            # 4. 解析响应
            json_text = self._extract_json_from_text(response_text)
            result = json.loads(json_text)
            
            # 5. 构建 QuestionResult
            scoring_point_results = []
            for spr_data in result.get("scoring_point_results", []):
                point_index = spr_data.get("point_index", 1) - 1
                if 0 <= point_index < len(rubric.scoring_points):
                    sp = rubric.scoring_points[point_index]
                else:
                    # 创建临时得分点
                    sp = ScoringPoint(
                        description=spr_data.get("description", ""),
                        score=spr_data.get("max_score", 0),
                        is_required=True,
                    )
                
                scoring_point_results.append(ScoringPointResult(
                    scoring_point=sp,
                    awarded=spr_data.get("awarded", 0),
                    evidence=spr_data.get("evidence", ""),
                ))
            
            question_result = QuestionResult(
                question_id=question_id,
                score=result.get("total_score", 0),
                max_score=result.get("max_score", rubric.max_score),
                confidence=result.get("confidence", 0.8),
                feedback=result.get("feedback", ""),
                scoring_point_results=scoring_point_results,
                page_indices=[],
                is_cross_page=False,
                student_answer=student_answer,
            )
            
            logger.info(
                f"题目 {question_id} 评分完成: "
                f"{question_result.score}/{question_result.max_score}, "
                f"置信度: {question_result.confidence}"
            )
            
            return question_result
            
        except json.JSONDecodeError as e:
            logger.error(f"得分点评分 JSON 解析失败: {e}")
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=rubric.max_score,
                confidence=0.0,
                feedback=f"评分解析失败: {str(e)}",
                scoring_point_results=[],
                page_indices=[],
                is_cross_page=False,
                student_answer=student_answer,
            )
        except Exception as e:
            logger.error(f"得分点评分失败: {e}", exc_info=True)
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=rubric.max_score,
                confidence=0.0,
                feedback=f"评分失败: {str(e)}",
                scoring_point_results=[],
                page_indices=[],
                is_cross_page=False,
                student_answer=student_answer,
            )

    async def grade_page_with_dynamic_rubric(
        self,
        image: bytes,
        page_index: int = 0,
        parsed_rubric: Optional[Dict[str, Any]] = None,
    ) -> PageGradingResult:
        """
        使用动态评分标准批改单页 (Requirements 1.1, 1.2, 1.3)
        
        集成 RubricRegistry 和 GradingSkills，实现：
        1. 识别页面中的题目编号
        2. 为每道题动态获取评分标准
        3. 逐一核对得分点
        4. 支持另类解法
        
        Args:
            image: 图像字节
            page_index: 页码索引
            parsed_rubric: 解析后的评分标准（可选，用于兼容旧接口）
            
        Returns:
            PageGradingResult: 包含详细得分点明细的页面批改结果
        """
        logger.info(f"开始批改第 {page_index + 1} 页（使用动态评分标准）")
        
        # 1. 首先进行基础批改，获取题目编号和学生答案
        basic_result = await self.grade_page(
            image=image,
            rubric="",  # 先不传评分标准，只做识别
            max_score=100.0,
            parsed_rubric=parsed_rubric,
        )
        
        # 2. 如果是空白页，直接返回
        if basic_result.get("is_blank_page", False):
            return PageGradingResult(
                page_index=page_index,
                question_results=[],
                student_info=None,
                is_blank_page=True,
                raw_response=json.dumps(basic_result, ensure_ascii=False),
            )
        
        # 3. 提取学生信息
        student_info = None
        if basic_result.get("student_info"):
            si = basic_result["student_info"]
            student_info = StudentInfo(
                student_id=si.get("student_id"),
                student_name=si.get("name"),
                confidence=0.8,
            )
        
        # 4. 对每道题进行得分点逐一核对评分
        question_results = []
        for q_detail in basic_result.get("question_details", []):
            question_id = q_detail.get("question_id", "")
            student_answer = q_detail.get("student_answer", "")
            
            if not question_id:
                continue
            
            # 使用得分点核对方式评分
            if self._rubric_registry:
                q_result = await self.grade_question_with_scoring_points(
                    question_id=question_id,
                    student_answer=student_answer,
                    image=image,
                )
                q_result.page_indices = [page_index]
            else:
                # 如果没有 RubricRegistry，使用基础结果
                q_result = QuestionResult(
                    question_id=question_id,
                    score=q_detail.get("score", 0),
                    max_score=q_detail.get("max_score", 0),
                    confidence=basic_result.get("confidence", 0.8),
                    feedback=q_detail.get("feedback", ""),
                    scoring_point_results=[],
                    page_indices=[page_index],
                    is_cross_page=False,
                    student_answer=student_answer,
                )
            
            question_results.append(q_result)
        
        # 5. 构建页面批改结果
        page_result = PageGradingResult(
            page_index=page_index,
            question_results=question_results,
            student_info=student_info,
            is_blank_page=False,
            raw_response=json.dumps(basic_result, ensure_ascii=False),
        )
        
        total_score = sum(qr.score for qr in question_results)
        total_max = sum(qr.max_score for qr in question_results)
        
        logger.info(
            f"第 {page_index + 1} 页批改完成: "
            f"{total_score}/{total_max}, "
            f"共 {len(question_results)} 道题"
        )
        
        return page_result

    def _format_rubric_for_prompt(
        self,
        rubric: QuestionRubric,
    ) -> str:
        """
        将 QuestionRubric 格式化为提示词中使用的文本
        
        Args:
            rubric: 评分标准对象
            
        Returns:
            str: 格式化的评分标准文本
        """
        lines = [
            f"第{rubric.question_id}题 (满分{rubric.max_score}分):",
            f"  题目: {rubric.question_text[:200]}..." if len(rubric.question_text) > 200 else f"  题目: {rubric.question_text}",
        ]
        
        # 添加得分点
        if rubric.scoring_points:
            lines.append("  得分点:")
            for sp in rubric.scoring_points:
                required = "【必须】" if sp.is_required else "【可选】"
                lines.append(f"    - {required} {sp.description} ({sp.score}分)")
        
        # 添加标准答案
        if rubric.standard_answer:
            answer_preview = rubric.standard_answer[:150] + "..." if len(rubric.standard_answer) > 150 else rubric.standard_answer
            lines.append(f"  标准答案: {answer_preview}")
        
        # 添加另类解法 (Requirement 1.3)
        if rubric.alternative_solutions:
            lines.append("  另类解法:")
            for alt in rubric.alternative_solutions:
                lines.append(f"    - {alt.description} (最高{alt.max_score}分)")
                lines.append(f"      条件: {alt.scoring_conditions}")
        
        return "\n".join(lines)

    async def build_dynamic_rubric_context(
        self,
        question_ids: List[str],
    ) -> str:
        """
        为指定题目列表构建动态评分标准上下文
        
        Args:
            question_ids: 题目编号列表
            
        Returns:
            str: 格式化的评分标准上下文文本
        """
        if not self._rubric_registry:
            return ""
        
        rubric_texts = []
        for qid in question_ids:
            rubric = await self.get_rubric_for_question(qid)
            if rubric:
                rubric_texts.append(self._format_rubric_for_prompt(rubric))
        
        if not rubric_texts:
            return ""
        
        total_score = self._rubric_registry.total_score
        return f"评分标准（总分{total_score}分）：\n\n" + "\n\n".join(rubric_texts)


    # ==================== 得分点明细生成 (Requirement 1.2) ====================
    
    def _create_scoring_point_results_from_response(
        self,
        response_data: Dict[str, Any],
        rubric: QuestionRubric,
    ) -> List[ScoringPointResult]:
        """
        从 LLM 响应创建得分点明细列表 (Requirement 1.2)
        
        为每个得分点记录得分情况，生成详细的得分点明细。
        
        Args:
            response_data: LLM 响应数据
            rubric: 评分标准
            
        Returns:
            List[ScoringPointResult]: 得分点明细列表
        """
        scoring_point_results = []
        response_points = response_data.get("scoring_point_results", [])
        
        # 确保每个评分标准中的得分点都有对应的结果
        for i, sp in enumerate(rubric.scoring_points):
            # 查找对应的响应数据
            matched_response = None
            for rp in response_points:
                # 通过索引或描述匹配
                if rp.get("point_index") == i + 1:
                    matched_response = rp
                    break
                if rp.get("description", "").strip() == sp.description.strip():
                    matched_response = rp
                    break
            
            if matched_response:
                awarded = matched_response.get("awarded", 0)
                evidence = matched_response.get("evidence", "")
            else:
                # 如果没有匹配的响应，标记为未评估
                awarded = 0
                evidence = "未评估"
            
            scoring_point_results.append(ScoringPointResult(
                scoring_point=sp,
                awarded=awarded,
                evidence=evidence,
            ))
        
        return scoring_point_results
    
    def generate_scoring_point_summary(
        self,
        scoring_point_results: List[ScoringPointResult],
    ) -> str:
        """
        生成得分点明细摘要 (Requirement 1.2)
        
        Args:
            scoring_point_results: 得分点明细列表
            
        Returns:
            str: 得分点明细摘要文本
        """
        if not scoring_point_results:
            return "无得分点明细"
        
        lines = ["得分点明细:"]
        total_awarded = 0
        total_max = 0
        
        for i, spr in enumerate(scoring_point_results, 1):
            sp = spr.scoring_point
            status = "✓" if spr.awarded >= sp.score else ("△" if spr.awarded > 0 else "✗")
            required_mark = "【必须】" if sp.is_required else "【可选】"
            
            lines.append(
                f"  {i}. {status} {required_mark} {sp.description}: "
                f"{spr.awarded}/{sp.score}分"
            )
            if spr.evidence:
                lines.append(f"      证据: {spr.evidence[:100]}...")
            
            total_awarded += spr.awarded
            total_max += sp.score
        
        lines.append(f"  总计: {total_awarded}/{total_max}分")
        
        return "\n".join(lines)
    
    async def grade_with_detailed_scoring_points(
        self,
        image: bytes,
        question_id: str,
        page_index: int = 0,
    ) -> QuestionResult:
        """
        使用详细得分点核对方式评分 (Requirement 1.2)
        
        这是一个完整的评分流程：
        1. 视觉分析提取学生答案
        2. 动态获取评分标准
        3. 逐一核对每个得分点
        4. 生成详细的得分点明细
        
        Args:
            image: 题目图像
            question_id: 题目编号
            page_index: 页码索引
            
        Returns:
            QuestionResult: 包含详细得分点明细的评分结果
        """
        # 1. 获取评分标准
        rubric = await self.get_rubric_for_question(question_id)
        if rubric is None:
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=0.0,
                confidence=0.0,
                feedback="无法获取评分标准",
                scoring_point_results=[],
                page_indices=[page_index],
                is_cross_page=False,
                student_answer="",
            )
        
        # 2. 视觉分析提取学生答案
        img_b64 = base64.b64encode(image).decode('utf-8') if isinstance(image, bytes) else image
        
        extraction_prompt = f"""请分析这张学生答题图像，提取第{question_id}题的学生答案。

任务：
1. 找到第{question_id}题的学生作答内容
2. 详细描述学生写了什么（公式、文字、图表、计算过程等）
3. 客观描述，不要评分

输出格式（JSON）：
```json
{{
    "question_id": "{question_id}",
    "student_answer": "学生答案的详细描述",
    "has_content": true,
    "content_type": "计算/文字/图表/混合"
}}
```"""
        
        try:
            extraction_response = await self._call_vision_api(img_b64, extraction_prompt)
            extraction_json = self._extract_json_from_text(extraction_response)
            extraction_data = json.loads(extraction_json)
            student_answer = extraction_data.get("student_answer", "")
        except Exception as e:
            logger.warning(f"学生答案提取失败: {e}")
            student_answer = "无法提取学生答案"
        
        # 3. 构建得分点核对提示词
        prompt = self._build_scoring_point_prompt(rubric, student_answer)
        
        # 4. 调用 LLM 进行得分点核对
        try:
            response_text = await self._call_vision_api(img_b64, prompt)
            json_text = self._extract_json_from_text(response_text)
            result_data = json.loads(json_text)
            
            # 5. 创建得分点明细
            scoring_point_results = self._create_scoring_point_results_from_response(
                result_data, rubric
            )
            
            # 6. 生成反馈
            feedback = result_data.get("feedback", "")
            scoring_summary = self.generate_scoring_point_summary(scoring_point_results)
            full_feedback = f"{feedback}\n\n{scoring_summary}"
            
            return QuestionResult(
                question_id=question_id,
                score=result_data.get("total_score", 0),
                max_score=result_data.get("max_score", rubric.max_score),
                confidence=result_data.get("confidence", 0.8),
                feedback=full_feedback,
                scoring_point_results=scoring_point_results,
                page_indices=[page_index],
                is_cross_page=False,
                student_answer=student_answer,
            )
            
        except Exception as e:
            logger.error(f"详细得分点评分失败: {e}", exc_info=True)
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=rubric.max_score,
                confidence=0.0,
                feedback=f"评分失败: {str(e)}",
                scoring_point_results=[],
                page_indices=[page_index],
                is_cross_page=False,
                student_answer=student_answer,
            )


    # ==================== 另类解法支持 (Requirement 1.3) ====================
    
    def _build_alternative_solution_prompt(
        self,
        rubric: QuestionRubric,
        student_answer: str,
    ) -> str:
        """
        构建另类解法检测提示词 (Requirement 1.3)
        
        Args:
            rubric: 评分标准
            student_answer: 学生答案描述
            
        Returns:
            str: 另类解法检测提示词
        """
        if not rubric.alternative_solutions:
            return ""
        
        alt_solutions_text = ""
        for i, alt in enumerate(rubric.alternative_solutions, 1):
            alt_solutions_text += f"""
### 另类解法 {i}
- 描述: {alt.description}
- 评分条件: {alt.scoring_conditions}
- 最高分: {alt.max_score}分
"""
        
        return f"""请判断学生是否使用了另类解法。

## 题目信息
- 题号: {rubric.question_id}
- 满分: {rubric.max_score}分

## 标准答案
{rubric.standard_answer}

## 可接受的另类解法
{alt_solutions_text}

## 学生答案
{student_answer}

## 任务
1. 判断学生是否使用了标准解法
2. 如果不是标准解法，判断是否使用了某个另类解法
3. 如果使用了另类解法，判断是否满足评分条件

## 输出格式（JSON）
```json
{{
    "uses_standard_solution": true/false,
    "uses_alternative_solution": true/false,
    "alternative_solution_index": null 或 1/2/3...,
    "alternative_solution_description": "使用的另类解法描述",
    "meets_scoring_conditions": true/false,
    "condition_analysis": "评分条件分析",
    "recommended_max_score": 建议的最高分
}}
```"""

    async def detect_alternative_solution(
        self,
        question_id: str,
        student_answer: str,
        image: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        检测学生是否使用了另类解法 (Requirement 1.3)
        
        Args:
            question_id: 题目编号
            student_answer: 学生答案描述
            image: 可选的题目图像
            
        Returns:
            Dict: 另类解法检测结果
        """
        # 获取评分标准
        rubric = await self.get_rubric_for_question(question_id)
        if rubric is None or not rubric.alternative_solutions:
            return {
                "uses_standard_solution": True,
                "uses_alternative_solution": False,
                "alternative_solution_index": None,
                "alternative_solution_description": None,
                "meets_scoring_conditions": False,
                "condition_analysis": "无另类解法可检测",
                "recommended_max_score": rubric.max_score if rubric else 0,
            }
        
        # 构建检测提示词
        prompt = self._build_alternative_solution_prompt(rubric, student_answer)
        
        try:
            if image:
                img_b64 = base64.b64encode(image).decode('utf-8') if isinstance(image, bytes) else image
                response_text = await self._call_vision_api(img_b64, prompt)
            else:
                response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                response_text = self._extract_text_from_response(response.content)
            
            json_text = self._extract_json_from_text(response_text)
            result = json.loads(json_text)
            
            logger.info(
                f"题目 {question_id} 另类解法检测: "
                f"标准解法={result.get('uses_standard_solution')}, "
                f"另类解法={result.get('uses_alternative_solution')}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"另类解法检测失败: {e}")
            return {
                "uses_standard_solution": True,
                "uses_alternative_solution": False,
                "alternative_solution_index": None,
                "alternative_solution_description": None,
                "meets_scoring_conditions": False,
                "condition_analysis": f"检测失败: {str(e)}",
                "recommended_max_score": rubric.max_score,
            }

    async def grade_with_alternative_solution_support(
        self,
        image: bytes,
        question_id: str,
        page_index: int = 0,
    ) -> QuestionResult:
        """
        支持另类解法的完整评分流程 (Requirement 1.3)
        
        这是一个增强的评分流程：
        1. 视觉分析提取学生答案
        2. 检测是否使用另类解法
        3. 根据解法类型选择评分标准
        4. 逐一核对得分点
        5. 生成详细的评分结果
        
        Args:
            image: 题目图像
            question_id: 题目编号
            page_index: 页码索引
            
        Returns:
            QuestionResult: 包含另类解法信息的评分结果
        """
        # 1. 获取评分标准
        rubric = await self.get_rubric_for_question(question_id)
        if rubric is None:
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=0.0,
                confidence=0.0,
                feedback="无法获取评分标准",
                scoring_point_results=[],
                page_indices=[page_index],
                is_cross_page=False,
                student_answer="",
            )
        
        # 2. 视觉分析提取学生答案
        img_b64 = base64.b64encode(image).decode('utf-8') if isinstance(image, bytes) else image
        
        extraction_prompt = f"""请分析这张学生答题图像，提取第{question_id}题的学生答案。

任务：
1. 找到第{question_id}题的学生作答内容
2. 详细描述学生的解题方法和步骤
3. 客观描述，不要评分

输出格式（JSON）：
```json
{{
    "question_id": "{question_id}",
    "student_answer": "学生答案的详细描述",
    "solution_method": "学生使用的解题方法描述",
    "has_content": true
}}
```"""
        
        try:
            extraction_response = await self._call_vision_api(img_b64, extraction_prompt)
            extraction_json = self._extract_json_from_text(extraction_response)
            extraction_data = json.loads(extraction_json)
            student_answer = extraction_data.get("student_answer", "")
            solution_method = extraction_data.get("solution_method", "")
        except Exception as e:
            logger.warning(f"学生答案提取失败: {e}")
            student_answer = "无法提取学生答案"
            solution_method = ""
        
        # 3. 检测另类解法
        alt_detection = await self.detect_alternative_solution(
            question_id=question_id,
            student_answer=f"{student_answer}\n解题方法: {solution_method}",
            image=image,
        )
        
        # 4. 根据解法类型构建评分提示词
        if alt_detection.get("uses_alternative_solution") and alt_detection.get("meets_scoring_conditions"):
            # 使用另类解法的评分标准
            alt_index = alt_detection.get("alternative_solution_index", 1) - 1
            if 0 <= alt_index < len(rubric.alternative_solutions):
                alt_solution = rubric.alternative_solutions[alt_index]
                scoring_context = f"""
## 学生使用了另类解法
- 解法描述: {alt_solution.description}
- 评分条件: {alt_solution.scoring_conditions}
- 最高分: {alt_solution.max_score}分

请根据另类解法的评分条件进行评分。
"""
                effective_max_score = alt_solution.max_score
            else:
                scoring_context = ""
                effective_max_score = rubric.max_score
        else:
            scoring_context = ""
            effective_max_score = rubric.max_score
        
        # 5. 构建完整的评分提示词
        prompt = self._build_scoring_point_prompt(rubric, student_answer)
        if scoring_context:
            prompt = prompt.replace("## 学生答案", f"{scoring_context}\n## 学生答案")
        
        # 6. 调用 LLM 进行评分
        try:
            response_text = await self._call_vision_api(img_b64, prompt)
            json_text = self._extract_json_from_text(response_text)
            result_data = json.loads(json_text)
            
            # 7. 创建得分点明细
            scoring_point_results = self._create_scoring_point_results_from_response(
                result_data, rubric
            )
            
            # 8. 生成反馈（包含另类解法信息）
            feedback_parts = [result_data.get("feedback", "")]
            
            if alt_detection.get("uses_alternative_solution"):
                if alt_detection.get("meets_scoring_conditions"):
                    feedback_parts.append(
                        f"\n【另类解法】学生使用了有效的另类解法: "
                        f"{alt_detection.get('alternative_solution_description', '')}"
                    )
                else:
                    feedback_parts.append(
                        f"\n【另类解法】学生尝试使用另类解法，但未满足评分条件: "
                        f"{alt_detection.get('condition_analysis', '')}"
                    )
            
            scoring_summary = self.generate_scoring_point_summary(scoring_point_results)
            feedback_parts.append(f"\n{scoring_summary}")
            
            full_feedback = "\n".join(feedback_parts)
            
            # 9. 确保分数不超过有效最高分
            final_score = min(result_data.get("total_score", 0), effective_max_score)
            
            return QuestionResult(
                question_id=question_id,
                score=final_score,
                max_score=effective_max_score,
                confidence=result_data.get("confidence", 0.8),
                feedback=full_feedback,
                scoring_point_results=scoring_point_results,
                page_indices=[page_index],
                is_cross_page=False,
                student_answer=student_answer,
            )
            
        except Exception as e:
            logger.error(f"另类解法评分失败: {e}", exc_info=True)
            return QuestionResult(
                question_id=question_id,
                score=0.0,
                max_score=rubric.max_score,
                confidence=0.0,
                feedback=f"评分失败: {str(e)}",
                scoring_point_results=[],
                page_indices=[page_index],
                is_cross_page=False,
                student_answer=student_answer,
            )
