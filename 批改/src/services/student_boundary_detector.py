"""学生边界检测器 - 基于批改结果智能判断学生边界

核心功能：
1. 从批改结果中提取学生标识信息
2. 通过题目序列循环检测学生边界
3. 计算边界置信度并标记低置信度边界
4. 集成现有 StudentIdentificationService
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from src.services.student_identification import (
    StudentIdentificationService,
    StudentInfo,
    PageAnalysis
)


logger = logging.getLogger(__name__)


@dataclass
class StudentBoundary:
    """学生边界信息"""
    student_key: str  # 学生标识（姓名/学号/代号）
    start_page: int  # 起始页码（从0开始）
    end_page: int  # 结束页码（包含）
    confidence: float  # 置信度 (0.0-1.0)
    needs_confirmation: bool  # 是否需要人工确认（置信度 < 0.8）
    student_info: Optional[StudentInfo] = None  # 学生详细信息
    detection_method: str = "unknown"  # 检测方法：student_info, question_cycle, hybrid


@dataclass
class BoundaryDetectionResult:
    """边界检测结果"""
    boundaries: List[StudentBoundary] = field(default_factory=list)
    total_students: int = 0
    unassigned_pages: List[int] = field(default_factory=list)
    detection_timestamp: datetime = field(default_factory=datetime.now)
    total_pages: int = 0


class StudentBoundaryDetector:
    """
    学生边界检测器
    
    基于批改结果智能判断学生边界，支持多种检测策略：
    1. 学生标识提取：从批改结果中提取学生姓名/学号
    2. 题目循环检测：通过题目序列的循环模式推断边界
    3. 混合策略：结合上述两种方法提高准确性
    """
    
    def __init__(
        self,
        student_identification_service: Optional[StudentIdentificationService] = None,
        confidence_threshold: float = 0.8
    ):
        """
        初始化学生边界检测器
        
        Args:
            student_identification_service: 学生识别服务实例（可选）
            confidence_threshold: 置信度阈值，低于此值需要人工确认
        """
        self.student_identification_service = student_identification_service
        self.confidence_threshold = confidence_threshold
    
    async def detect_boundaries(
        self,
        grading_results: List[Dict[str, Any]]
    ) -> BoundaryDetectionResult:
        """
        基于批改结果检测学生边界
        
        Args:
            grading_results: 批改结果列表，每个结果包含页面信息和批改内容
            
        Returns:
            BoundaryDetectionResult: 检测到的学生边界信息
        """
        if not grading_results:
            logger.warning("批改结果为空，无法检测学生边界")
            return BoundaryDetectionResult(total_pages=0)
        
        total_pages = len(grading_results)
        logger.info(f"开始检测学生边界，共 {total_pages} 页批改结果")
        
        # 第一步：尝试从批改结果中提取学生标识
        student_markers = self._extract_student_markers_from_results(grading_results)
        
        # 第二步：提取题目信息用于循环检测
        page_analyses = self._extract_page_analyses(grading_results)
        
        # 第三步：根据可用信息选择检测策略
        if self._has_reliable_student_markers(student_markers):
            # 策略1：基于学生标识
            boundaries = self._detect_by_student_markers(
                student_markers,
                total_pages
            )
            detection_method = "student_info"
        else:
            # 策略2：基于题目循环
            boundaries = self._detect_by_question_cycle(
                page_analyses,
                total_pages
            )
            detection_method = "question_cycle"
        
        # 第四步：计算置信度并标记低置信度边界
        boundaries = self._calculate_confidence(boundaries, student_markers, page_analyses)
        
        # 第五步：标记需要确认的边界
        for boundary in boundaries:
            boundary.needs_confirmation = boundary.confidence < self.confidence_threshold
            boundary.detection_method = detection_method
        
        # 第六步：识别未分配的页面
        assigned_pages = set()
        for boundary in boundaries:
            assigned_pages.update(range(boundary.start_page, boundary.end_page + 1))
        unassigned_pages = [i for i in range(total_pages) if i not in assigned_pages]
        
        result = BoundaryDetectionResult(
            boundaries=boundaries,
            total_students=len(boundaries),
            unassigned_pages=unassigned_pages,
            total_pages=total_pages
        )
        
        logger.info(
            f"边界检测完成：检测到 {result.total_students} 个学生，"
            f"未分配页面 {len(unassigned_pages)} 页"
        )
        
        return result
    
    def _extract_student_markers(
        self,
        result: Dict[str, Any]
    ) -> Optional[StudentInfo]:
        """
        从单个批改结果中提取学生标识
        
        这是一个独立的方法，用于从单个批改结果中提取学生信息。
        支持多种数据格式和字段位置。
        
        Args:
            result: 单个批改结果
            
        Returns:
            Optional[StudentInfo]: 提取到的学生信息，如果没有则返回 None
        """
        student_info = None
        
        # 方法1：直接从 student_info 字段提取
        if "student_info" in result and result["student_info"]:
            si = result["student_info"]
            if isinstance(si, dict):
                student_info = StudentInfo(
                    name=si.get("name"),
                    student_id=si.get("student_id"),
                    class_name=si.get("class_name"),
                    confidence=si.get("confidence", 0.0)
                )
            elif isinstance(si, StudentInfo):
                student_info = si
        
        # 方法2：从 metadata 中提取
        elif "metadata" in result:
            metadata = result["metadata"]
            if isinstance(metadata, dict):
                if "student_name" in metadata or "student_id" in metadata:
                    student_info = StudentInfo(
                        name=metadata.get("student_name"),
                        student_id=metadata.get("student_id"),
                        confidence=metadata.get("student_confidence", 0.0)
                    )
        
        # 方法3：从 agent_trace 中提取
        elif "agent_trace" in result:
            trace = result.get("agent_trace", {})
            if isinstance(trace, dict) and "student_identification" in trace:
                si = trace["student_identification"]
                if isinstance(si, dict):
                    student_info = StudentInfo(
                        name=si.get("name"),
                        student_id=si.get("student_id"),
                        confidence=si.get("confidence", 0.0)
                    )
        
        return student_info
    
    def _extract_student_markers_from_results(
        self,
        grading_results: List[Dict[str, Any]]
    ) -> Dict[int, Optional[StudentInfo]]:
        """
        从批改结果中提取学生标识信息
        
        Args:
            grading_results: 批改结果列表
            
        Returns:
            Dict[int, Optional[StudentInfo]]: 页码 -> 学生信息的映射
        """
        student_markers = {}
        
        for i, result in enumerate(grading_results):
            student_info = self._extract_student_markers(result)
            student_markers[i] = student_info
        
        return student_markers
    
    def _detect_question_cycle(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Tuple[int, int]]:
        """
        通过题目序列循环检测学生边界
        
        这是一个独立的方法，用于检测题目编号的循环模式。
        当题目编号从大变小（如从5回到1）时，说明换了一个学生。
        
        Args:
            results: 批改结果列表
            
        Returns:
            List[Tuple[int, int]]: 每个学生的页面范围 [(start, end), ...]
        """
        if not results:
            return []
        
        # 提取页面分析信息
        page_analyses = self._extract_page_analyses(results)
        
        # 使用现有的 StudentIdentificationService 逻辑
        if self.student_identification_service:
            # 如果有 StudentIdentificationService，使用其检测逻辑
            boundaries = self.student_identification_service.detect_student_boundaries(
                page_analyses
            )
            return boundaries
        
        # 否则使用内置的简单检测逻辑
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
    
    def _extract_page_analyses(
        self,
        grading_results: List[Dict[str, Any]]
    ) -> List[PageAnalysis]:
        """
        从批改结果中提取页面分析信息（题目编号等）
        
        Args:
            grading_results: 批改结果列表
            
        Returns:
            List[PageAnalysis]: 页面分析结果列表
        """
        page_analyses = []
        
        for i, result in enumerate(grading_results):
            question_numbers = []
            first_question = None
            
            # 尝试从多个字段提取题目信息
            if "question_id" in result:
                qid = result["question_id"]
                if qid:
                    question_numbers.append(str(qid))
                    first_question = str(qid)
            
            if "question_numbers" in result:
                qns = result["question_numbers"]
                if isinstance(qns, list):
                    question_numbers.extend([str(q) for q in qns])
                    if not first_question and qns:
                        first_question = str(qns[0])
            
            # 从 metadata 中提取
            if "metadata" in result:
                metadata = result["metadata"]
                if isinstance(metadata, dict):
                    if "questions" in metadata:
                        qs = metadata["questions"]
                        if isinstance(qs, list):
                            question_numbers.extend([str(q) for q in qs])
                            if not first_question and qs:
                                first_question = str(qs[0])
            
            # 获取学生信息（如果有）
            student_info = None
            if i in self._extract_student_markers_from_results(grading_results):
                student_info = self._extract_student_markers_from_results(grading_results)[i]
            
            page_analyses.append(PageAnalysis(
                page_index=i,
                question_numbers=question_numbers,
                first_question=first_question,
                student_info=student_info
            ))
        
        return page_analyses
    
    def _has_reliable_student_markers(
        self,
        student_markers: Dict[int, Optional[StudentInfo]]
    ) -> bool:
        """
        判断是否有可靠的学生标识信息
        
        Args:
            student_markers: 页码 -> 学生信息的映射
            
        Returns:
            bool: 是否有足够可靠的学生标识
        """
        reliable_count = sum(
            1 for si in student_markers.values()
            if si and si.confidence >= 0.6 and (si.name or si.student_id)
        )
        
        # 至少有20%的页面有可靠的学生标识
        return reliable_count >= len(student_markers) * 0.2
    
    def _detect_by_student_markers(
        self,
        student_markers: Dict[int, Optional[StudentInfo]],
        total_pages: int
    ) -> List[StudentBoundary]:
        """
        基于学生标识检测边界
        
        Args:
            student_markers: 页码 -> 学生信息的映射
            total_pages: 总页数
            
        Returns:
            List[StudentBoundary]: 检测到的学生边界
        """
        boundaries = []
        current_student = None
        current_start = 0
        
        for page_idx in range(total_pages):
            student_info = student_markers.get(page_idx)
            
            # 检测到新学生
            if student_info and student_info.confidence >= 0.6:
                student_key = student_info.student_id or student_info.name
                
                # 检查是否是新学生（与当前学生不同）
                if current_student is None:
                    # 第一个学生
                    current_student = student_key
                    current_start = page_idx
                elif current_student != student_key:
                    # 不同的学生，保存当前边界
                    boundaries.append(StudentBoundary(
                        student_key=current_student,
                        start_page=current_start,
                        end_page=page_idx - 1,
                        confidence=0.0,  # 稍后计算
                        needs_confirmation=False,
                        student_info=student_markers.get(current_start)
                    ))
                    
                    # 开始新学生
                    current_student = student_key
                    current_start = page_idx
                # 如果是同一个学生，继续累积页面
        
        # 添加最后一个学生
        if current_student:
            boundaries.append(StudentBoundary(
                student_key=current_student,
                start_page=current_start,
                end_page=total_pages - 1,
                confidence=0.0,  # 稍后计算
                needs_confirmation=False,
                student_info=student_markers.get(current_start)
            ))
        
        return boundaries
    
    def _detect_by_question_cycle(
        self,
        page_analyses: List[PageAnalysis],
        total_pages: int
    ) -> List[StudentBoundary]:
        """
        基于题目循环检测边界
        
        使用 _detect_question_cycle 方法检测边界
        
        Args:
            page_analyses: 页面分析结果
            total_pages: 总页数
            
        Returns:
            List[StudentBoundary]: 检测到的学生边界
        """
        boundaries = []
        
        if not page_analyses:
            return boundaries
        
        # 使用题目循环检测逻辑
        # 将 page_analyses 转换为批改结果格式
        results = []
        for analysis in page_analyses:
            result = {
                "page_index": analysis.page_index,
                "question_numbers": analysis.question_numbers,
                "question_id": analysis.first_question
            }
            if analysis.student_info:
                result["student_info"] = analysis.student_info
            results.append(result)
        
        # 调用 _detect_question_cycle 方法
        boundary_ranges = self._detect_question_cycle(results)
        
        # 转换为 StudentBoundary 对象
        for idx, (start, end) in enumerate(boundary_ranges):
            student_count = idx + 1
            boundaries.append(StudentBoundary(
                student_key=f"学生{chr(65 + idx)}",
                start_page=start,
                end_page=end,
                confidence=0.0,  # 稍后计算
                needs_confirmation=False,
                student_info=StudentInfo(
                    name=f"学生{chr(65 + idx)}",
                    student_id=f"UNKNOWN_{student_count:03d}",
                    confidence=0.5,
                    is_placeholder=True
                )
            ))
        
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
        chinese_nums = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }
        if q in chinese_nums:
            return chinese_nums[q]
        
        # 尝试直接转换
        return int(q)
    
    def _calculate_confidence(
        self,
        boundaries: List[StudentBoundary],
        student_markers: Dict[int, Optional[StudentInfo]],
        page_analyses: List[PageAnalysis]
    ) -> List[StudentBoundary]:
        """
        计算每个边界的置信度
        
        置信度计算考虑：
        1. 学生标识的置信度
        2. 题目序列的连续性
        3. 边界的清晰度
        
        Args:
            boundaries: 待计算置信度的边界列表
            student_markers: 学生标识信息
            page_analyses: 页面分析结果
            
        Returns:
            List[StudentBoundary]: 更新了置信度的边界列表
        """
        for boundary in boundaries:
            confidence_scores = []
            
            # 因素1：学生标识置信度
            if boundary.student_info and not boundary.student_info.is_placeholder:
                confidence_scores.append(boundary.student_info.confidence)
            
            # 因素2：题目序列连续性
            question_continuity = self._calculate_question_continuity(
                boundary,
                page_analyses
            )
            confidence_scores.append(question_continuity)
            
            # 因素3：边界清晰度（是否有明确的学生标识变化）
            boundary_clarity = self._calculate_boundary_clarity(
                boundary,
                student_markers
            )
            confidence_scores.append(boundary_clarity)
            
            # 综合置信度（加权平均）
            if confidence_scores:
                boundary.confidence = sum(confidence_scores) / len(confidence_scores)
            else:
                boundary.confidence = 0.5  # 默认中等置信度
        
        return boundaries
    
    def _calculate_question_continuity(
        self,
        boundary: StudentBoundary,
        page_analyses: List[PageAnalysis]
    ) -> float:
        """
        计算题目序列的连续性得分
        
        Args:
            boundary: 学生边界
            page_analyses: 页面分析结果
            
        Returns:
            float: 连续性得分 (0.0-1.0)
        """
        if boundary.start_page >= len(page_analyses) or boundary.end_page >= len(page_analyses):
            return 0.5
        
        # 提取该学生范围内的题目编号
        question_numbers = []
        for i in range(boundary.start_page, boundary.end_page + 1):
            if i < len(page_analyses):
                analysis = page_analyses[i]
                for q in analysis.question_numbers:
                    try:
                        q_num = self._normalize_question_number(q)
                        question_numbers.append(q_num)
                    except ValueError:
                        continue
        
        if len(question_numbers) < 2:
            return 0.5
        
        # 计算连续性：相邻题目编号的差值
        gaps = []
        for i in range(len(question_numbers) - 1):
            gap = abs(question_numbers[i + 1] - question_numbers[i])
            gaps.append(gap)
        
        # 大部分差值为1表示连续性好
        continuous_count = sum(1 for gap in gaps if gap == 1)
        continuity_score = continuous_count / len(gaps) if gaps else 0.5
        
        return continuity_score
    
    def _calculate_boundary_clarity(
        self,
        boundary: StudentBoundary,
        student_markers: Dict[int, Optional[StudentInfo]]
    ) -> float:
        """
        计算边界清晰度得分
        
        Args:
            boundary: 学生边界
            student_markers: 学生标识信息
            
        Returns:
            float: 清晰度得分 (0.0-1.0)
        """
        # 检查起始页是否有明确的学生标识
        start_marker = student_markers.get(boundary.start_page)
        if start_marker and start_marker.confidence >= 0.6:
            return 0.9
        
        # 检查前一页是否有不同的学生标识
        if boundary.start_page > 0:
            prev_marker = student_markers.get(boundary.start_page - 1)
            if prev_marker and start_marker:
                if prev_marker.student_id != start_marker.student_id:
                    return 0.8
        
        # 默认中等清晰度
        return 0.6
