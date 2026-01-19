"""学生身份识别服务 - 基于题目顺序循环检测

核心逻辑：
1. 首先尝试识别学生信息（姓名/学号）
2. 如果无法识别学生信息，则识别当前页面的题目编号
3. 通过检测题目编号的"循环"来推断学生边界
   - 例如：题目顺序 1,2,3,4,1,2,3,4 表示有 2 个学生
4. 即使不知道学生具体信息，也用代号（学生A、学生B）标识
"""

import asyncio
import base64
import json
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage

from src.services.chat_model_factory import get_chat_model
from src.models.region import BoundingBox
from src.utils.coordinates import normalize_coordinates
from src.config.models import get_lite_model


logger = logging.getLogger(__name__)


@dataclass
class StudentInfo:
    """学生信息"""
    name: Optional[str] = None
    student_id: Optional[str] = None
    class_name: Optional[str] = None
    confidence: float = 0.0
    bounding_box: Optional[BoundingBox] = None
    is_placeholder: bool = False  # 是否为占位符（无法识别真实信息时使用代号）


@dataclass
class PageAnalysis:
    """页面分析结果"""
    page_index: int
    question_numbers: List[str] = field(default_factory=list)  # 该页包含的题目编号
    first_question: Optional[str] = None  # 第一道题的编号
    student_info: Optional[StudentInfo] = None
    is_cover_page: bool = False  # 是否为封面/说明页


@dataclass
class PageStudentMapping:
    """页面与学生的映射关系"""
    page_index: int
    student_info: StudentInfo
    is_first_page: bool = False


@dataclass
class BatchSegmentationResult:
    """批量分割结果"""
    total_pages: int
    student_count: int
    page_mappings: List[PageStudentMapping]
    unidentified_pages: List[int]


class StudentIdentificationService:
    """
    学生身份识别服务
    
    使用两阶段策略：
    1. 尝试识别学生信息（姓名/学号）
    2. 如果失败，通过题目顺序循环检测推断学生边界
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        if model_name is None:
            model_name = get_lite_model()
        self.llm = get_chat_model(
            api_key=api_key,
            model_name=model_name,
            temperature=0.1,
            purpose="vision",
            enable_thinking=False,
        )
        self.model_name = model_name
    
    async def analyze_page(
        self,
        image_data: bytes,
        page_index: int = 0,
        boundary_only: bool = False
    ) -> PageAnalysis:
        """
        分析单页：识别学生信息和题目编号
        
        Returns:
            PageAnalysis: 包含学生信息和题目编号的分析结果
        """
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        if boundary_only:
            prompt = """Analyze this exam page ONLY for boundary detection.
Return JSON only, no extra text.

Extract:
1. Up to 3 question numbers in order. If none, return [].
2. The first visible question number (string or null).
3. Whether this is a cover/instruction page (no answers).

Output JSON:
{
  "questions": {
    "numbers": ["1", "2", "3"],
    "first_question": "1"
  },
  "is_cover_page": false
}

Normalize question numbers (e.g., "Question 1" -> "1"). Ignore A/B/C/D options.
"""
        else:
            prompt = """Analyze this exam page.
Extract student info only if obvious, otherwise use null.
Extract question numbers in order and mark if it is a cover page.
Return JSON only, no extra text.

Output JSON:
{
  "student_info": {
    "found": true/false,
    "name": "name or null",
    "student_id": "id or null",
    "class_name": "class or null",
    "confidence": 0.0
  },
  "questions": {
    "numbers": ["1", "2", "3"],
    "first_question": "1"
  },
  "is_cover_page": false
}

Normalize question numbers (e.g., "Question 1" -> "1"). Ignore A/B/C/D options.
"""

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": f"data:image/png;base64,{image_b64}"}
            ]
        )
        
        try:
            # 添加重试机制处理 503 错误
            max_retries = 3
            retry_delay = 5
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    response = await self.llm.ainvoke([message])
                    break
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    if "503" in error_str or "overloaded" in error_str.lower():
                        if attempt < max_retries - 1:
                            logger.warning(f"LLM API 过载，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                    raise
            else:
                raise last_error
            
            # 处理 response.content 可能是列表的情况
            result_text = response.content
            if isinstance(result_text, list):
                text_parts = []
                for item in result_text:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])
                result_text = "".join(text_parts)
            elif not isinstance(result_text, str):
                result_text = str(result_text) if result_text else ""
            
            # 提取 JSON
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            
            data = json.loads(result_text)
            
            # 解析学生信息
            student_info = None
            if not boundary_only:
                si = data.get("student_info", {})
                if si.get("found") and (si.get("name") or si.get("student_id")):
                    student_info = StudentInfo(
                        name=si.get("name"),
                        student_id=si.get("student_id"),
                        class_name=si.get("class_name"),
                        confidence=si.get("confidence", 0.0)
                    )
            
            # 解析题目编号
            questions = data.get("questions", {})
            question_numbers = questions.get("numbers", [])
            first_question = questions.get("first_question")
            if boundary_only and question_numbers:
                question_numbers = question_numbers[:3]
                if not first_question:
                    first_question = question_numbers[0]
            
            return PageAnalysis(
                page_index=page_index,
                question_numbers=question_numbers,
                first_question=first_question,
                student_info=student_info,
                is_cover_page=data.get("is_cover_page", False)
            )
            
        except Exception as e:
            logger.error(f"页面分析失败 (page {page_index}): {str(e)}")
            return PageAnalysis(page_index=page_index)
    
    def detect_student_boundaries(
        self,
        page_analyses: List[PageAnalysis]
    ) -> List[Tuple[int, int]]:
        """
        通过题目顺序循环检测学生边界
        
        逻辑：
        - 如果题目编号出现"回退"（如从大变小），说明换了一个学生
        - 例如：页面题目 [3,4], [5,6], [1,2], [3,4] -> 在第3页检测到循环
        
        Returns:
            List[Tuple[int, int]]: 每个学生的页面范围 [(start, end), ...]
        """
        if not page_analyses:
            return []
        
        boundaries = []
        current_start = 0
        last_max_question = 0
        
        for i, analysis in enumerate(page_analyses):
            # 跳过封面页
            if analysis.is_cover_page:
                continue
            
            # 获取当前页的第一道题编号
            first_q = analysis.first_question
            if not first_q:
                continue
            
            try:
                # 尝试转换为数字进行比较
                first_q_num = self._normalize_question_number(first_q)
                
                # 检测循环：题目编号回退到较小值
                if first_q_num < last_max_question and first_q_num <= 2:
                    # 发现新学生的开始
                    if i > current_start:
                        boundaries.append((current_start, i - 1))
                    current_start = i
                    last_max_question = first_q_num
                else:
                    # 更新最大题号
                    for q in analysis.question_numbers:
                        q_num = self._normalize_question_number(q)
                        last_max_question = max(last_max_question, q_num)
                        
            except ValueError:
                continue
        
        # 添加最后一个学生的范围
        if current_start < len(page_analyses):
            boundaries.append((current_start, len(page_analyses) - 1))
        
        return boundaries
    
    def _normalize_question_number(self, q: str) -> int:
        """将题目编号标准化为数字"""
        if not q:
            return 0
        
        # 移除常见前缀
        q = q.lower().strip()
        for prefix in ['question', 'q', '第', '题', 'no.', 'no', '#']:
            q = q.replace(prefix, '')
        q = q.strip()
        
        # 中文数字转换
        chinese_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                       '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
        if q in chinese_nums:
            return chinese_nums[q]
        
        # 尝试直接转换
        return int(q)
    
    async def segment_batch_document(
        self,
        images_data: List[bytes],
        progress_callback: Optional[callable] = None
    ) -> BatchSegmentationResult:
        """
        分割多学生合卷文档
        
        策略：
        1. 分析所有页面，提取学生信息和题目编号
        2. 优先使用学生信息进行分组
        3. 如果无学生信息，使用题目顺序循环检测
        4. 为无法识别的学生分配代号
        """
        logger.info(f"开始批量文档分割，共 {len(images_data)} 页")
        
        # 第一阶段：分析所有页面 (并行处理)
        semaphore = asyncio.Semaphore(5)  # 限制并发数为 5，避免 API 过载
        print(f"DEBUG: Starting parallel analysis of {len(images_data)} pages")
        
        async def analyzed_page_with_semaphore(image_data, i):
            async with semaphore:
                print(f"DEBUG: Analyzing page {i}...")
                analysis = await self.analyze_page(image_data, i)
                print(f"DEBUG: Page {i} analysis complete")
                if progress_callback:
                    await progress_callback(i + 1, len(images_data))
                return analysis

        tasks = [analyzed_page_with_semaphore(img, i) for i, img in enumerate(images_data)]
        page_analyses = await asyncio.gather(*tasks)
        
        # 按索引排序，确保顺序正确
        page_analyses.sort(key=lambda x: x.page_index)
        
        for analysis in page_analyses:
            logger.info(
                f"页面 {analysis.page_index}: questions={analysis.question_numbers}, "
                f"first={analysis.first_question}, "
                f"student={analysis.student_info.name if analysis.student_info else 'None'}"
            )
        
        # 第二阶段：检测学生边界
        # 首先检查是否有明确的学生信息
        has_student_info = any(
            a.student_info and a.student_info.confidence >= 0.6 
            for a in page_analyses
        )
        
        if has_student_info:
            # 使用学生信息分组
            return self._segment_by_student_info(page_analyses)
        else:
            # 使用题目顺序循环检测
            return self._segment_by_question_cycle(page_analyses)

    def segment_from_analyses(
        self,
        page_analyses: List[PageAnalysis]
    ) -> BatchSegmentationResult:
        """
        基于已有页面分析结果执行分组（避免重复调用模型）

        Args:
            page_analyses: 页面分析结果列表

        Returns:
            BatchSegmentationResult: 分组结果
        """
        if not page_analyses:
            return BatchSegmentationResult(
                total_pages=0,
                student_count=0,
                page_mappings=[],
                unidentified_pages=[]
            )

        page_analyses.sort(key=lambda x: x.page_index)

        has_student_info = any(
            a.student_info and a.student_info.confidence >= 0.6
            for a in page_analyses
        )

        if has_student_info:
            return self._segment_by_student_info(page_analyses)
        return self._segment_by_question_cycle(page_analyses)
    
    def _segment_by_student_info(
        self,
        page_analyses: List[PageAnalysis]
    ) -> BatchSegmentationResult:
        """基于学生信息分组"""
        page_mappings = []
        students_seen = {}
        current_student = None
        
        for analysis in page_analyses:
            if analysis.student_info and analysis.student_info.confidence >= 0.6:
                key = analysis.student_info.student_id or analysis.student_info.name
                if key not in students_seen:
                    students_seen[key] = analysis.student_info
                current_student = students_seen[key]
                is_first = key not in students_seen
            
            if current_student:
                page_mappings.append(PageStudentMapping(
                    page_index=analysis.page_index,
                    student_info=current_student,
                    is_first_page=(analysis.student_info is not None)
                ))
        
        return BatchSegmentationResult(
            total_pages=len(page_analyses),
            student_count=len(students_seen),
            page_mappings=page_mappings,
            unidentified_pages=[]
        )
    
    def _segment_by_question_cycle(
        self,
        page_analyses: List[PageAnalysis]
    ) -> BatchSegmentationResult:
        """基于题目顺序循环检测分组"""
        boundaries = self.detect_student_boundaries(page_analyses)
        
        logger.info(f"检测到 {len(boundaries)} 个学生边界: {boundaries}")
        
        page_mappings = []
        student_count = 0
        
        for idx, (start, end) in enumerate(boundaries):
            student_count += 1
            # 创建占位符学生信息
            placeholder = StudentInfo(
                name=f"学生{chr(65 + idx)}",  # 学生A, 学生B, ...
                student_id=f"UNKNOWN_{idx + 1:03d}",
                confidence=0.5,
                is_placeholder=True
            )
            
            for page_idx in range(start, end + 1):
                page_mappings.append(PageStudentMapping(
                    page_index=page_idx,
                    student_info=placeholder,
                    is_first_page=(page_idx == start)
                ))
        
        # 处理未分配的页面
        assigned_pages = set(m.page_index for m in page_mappings)
        unidentified = [i for i in range(len(page_analyses)) if i not in assigned_pages]
        
        return BatchSegmentationResult(
            total_pages=len(page_analyses),
            student_count=student_count,
            page_mappings=page_mappings,
            unidentified_pages=unidentified
        )
    
    def group_pages_by_student(
        self,
        batch_result: BatchSegmentationResult
    ) -> dict[str, List[int]]:
        """将页面按学生分组"""
        groups: dict[str, List[int]] = {}
        
        for mapping in batch_result.page_mappings:
            student_key = (
                mapping.student_info.student_id or 
                mapping.student_info.name or 
                f"unknown_{mapping.page_index}"
            )
            
            if student_key not in groups:
                groups[student_key] = []
            groups[student_key].append(mapping.page_index)
        
        return groups
