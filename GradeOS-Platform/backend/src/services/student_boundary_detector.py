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
    4. 学生结果聚合：正确聚合学生范围内的所有题目，处理跨页题目
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
        
        # 使用内置的简单检测逻辑
        boundaries = []
        current_start = 0
        last_max_question = 0
        
        for i, result in enumerate(results):
            # 获取题目编号
            question_numbers = result.get("question_numbers", [])
            first_q = result.get("question_id") or result.get("first_question")
            
            if not first_q and question_numbers:
                first_q = question_numbers[0] if question_numbers else None
            
            if not first_q:
                continue
            
            try:
                # 尝试转换为数字进行比较
                first_q_num = self._normalize_question_number(str(first_q))
                
                # 检测循环：题目编号回退到较小值
                if first_q_num < last_max_question and first_q_num <= 2:
                    # 发现新学生的开始
                    if i > current_start:
                        boundaries.append((current_start, i - 1))
                    current_start = i
                    last_max_question = first_q_num
                else:
                    # 更新最大题号
                    for q in question_numbers:
                        try:
                            q_num = self._normalize_question_number(str(q))
                            last_max_question = max(last_max_question, q_num)
                        except ValueError:
                            continue
                        
            except ValueError:
                continue
        
        # 添加最后一个学生的范围
        if current_start < len(results):
            boundaries.append((current_start, len(results) - 1))
        
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
        基于学生标识检测边界（改进版）
        
        改进点：
        1. 更智能的学生切换检测：考虑置信度和连续性
        2. 处理学生信息缺失的页面：使用前向填充策略
        3. 检测异常切换：避免频繁的学生切换
        
        Args:
            student_markers: 页码 -> 学生信息的映射
            total_pages: 总页数
            
        Returns:
            List[StudentBoundary]: 检测到的学生边界
        """
        boundaries = []
        current_student = None
        current_start = 0
        student_page_counts = {}  # 统计每个学生的页面数
        last_reliable_student = None  # 最后一个可靠的学生标识
        
        logger.info(f"开始基于学生标识检测边界，共 {total_pages} 页")
        
        for page_idx in range(total_pages):
            student_info = student_markers.get(page_idx)
            
            # 检测到学生信息
            if student_info and student_info.confidence >= 0.6:
                student_key = student_info.student_id or student_info.name
                
                # 第一个学生
                if current_student is None:
                    current_student = student_key
                    current_start = page_idx
                    last_reliable_student = student_info
                    logger.info(f"检测到第一个学生：{student_key}，起始页 {page_idx}")
                
                # 检测到不同的学生
                elif current_student != student_key:
                    # 验证是否是真正的学生切换
                    # 条件1：新学生的置信度足够高
                    # 条件2：当前学生已经有足够的页面（避免误判）
                    pages_in_current = page_idx - current_start
                    
                    if student_info.confidence >= 0.7 and pages_in_current >= 3:
                        # 确认是新学生，保存当前边界
                        boundaries.append(StudentBoundary(
                            student_key=current_student,
                            start_page=current_start,
                            end_page=page_idx - 1,
                            confidence=0.0,  # 稍后计算
                            needs_confirmation=False,
                            student_info=last_reliable_student
                        ))
                        
                        # 记录页面数
                        student_page_counts[current_student] = pages_in_current
                        
                        logger.info(
                            f"检测到学生切换：{current_student} -> {student_key}，"
                            f"页面范围 [{current_start}, {page_idx - 1}]"
                        )
                        
                        # 开始新学生
                        current_student = student_key
                        current_start = page_idx
                        last_reliable_student = student_info
                    
                    elif student_info.confidence >= 0.8 and pages_in_current >= 1:
                        # 高置信度的新学生，即使当前学生页面较少也切换
                        boundaries.append(StudentBoundary(
                            student_key=current_student,
                            start_page=current_start,
                            end_page=page_idx - 1,
                            confidence=0.0,
                            needs_confirmation=False,
                            student_info=last_reliable_student
                        ))
                        
                        student_page_counts[current_student] = pages_in_current
                        
                        logger.info(
                            f"检测到高置信度学生切换：{current_student} -> {student_key}，"
                            f"页面范围 [{current_start}, {page_idx - 1}]"
                        )
                        
                        current_student = student_key
                        current_start = page_idx
                        last_reliable_student = student_info
                    
                    else:
                        # 置信度不够或页面太少，可能是误判，继续当前学生
                        logger.debug(
                            f"页面 {page_idx} 检测到学生 {student_key}，"
                            f"但置信度 {student_info.confidence} 或页面数 {pages_in_current} 不足，"
                            f"继续当前学生 {current_student}"
                        )
                
                # 同一个学生，继续累积页面
                else:
                    # 更新最后可靠的学生信息（使用置信度更高的）
                    if student_info.confidence > last_reliable_student.confidence:
                        last_reliable_student = student_info
            
            # 没有检测到学生信息，使用前向填充策略
            else:
                # 如果当前有学生，继续归属到当前学生
                if current_student is not None:
                    logger.debug(f"页面 {page_idx} 无学生信息，归属到当前学生 {current_student}")
                else:
                    # 如果还没有检测到任何学生，标记为待定
                    logger.debug(f"页面 {page_idx} 无学生信息，且尚未检测到学生")
        
        # 添加最后一个学生
        if current_student:
            pages_in_current = total_pages - current_start
            boundaries.append(StudentBoundary(
                student_key=current_student,
                start_page=current_start,
                end_page=total_pages - 1,
                confidence=0.0,  # 稍后计算
                needs_confirmation=False,
                student_info=last_reliable_student
            ))
            student_page_counts[current_student] = pages_in_current
            
            logger.info(
                f"添加最后一个学生：{current_student}，"
                f"页面范围 [{current_start}, {total_pages - 1}]"
            )
        
        # 验证检测结果的合理性
        if boundaries:
            # 检查是否有异常短的学生范围
            for boundary in boundaries:
                pages = boundary.end_page - boundary.start_page + 1
                if pages < 2:
                    logger.warning(
                        f"检测到异常短的学生范围：{boundary.student_key}，"
                        f"仅 {pages} 页，可能需要人工确认"
                    )
            
            # 统计信息
            avg_pages = sum(student_page_counts.values()) / len(student_page_counts)
            logger.info(
                f"学生边界检测完成：共 {len(boundaries)} 个学生，"
                f"平均每个学生 {avg_pages:.1f} 页"
            )
        
        return boundaries
    
    def _detect_by_question_cycle(
        self,
        page_analyses: List[PageAnalysis],
        total_pages: int
    ) -> List[StudentBoundary]:
        """
        基于题目循环检测边界（改进版）
        
        改进点：
        1. 更智能的循环检测：考虑题目序列的连续性和跳跃
        2. 多重信号融合：结合题目回退、题目密度、页面特征
        3. 自适应阈值：根据题目分布动态调整检测阈值
        
        Args:
            page_analyses: 页面分析结果
            total_pages: 总页数
            
        Returns:
            List[StudentBoundary]: 检测到的学生边界
        """
        boundaries = []
        
        if not page_analyses:
            # 如果没有页面分析结果，返回单个学生边界
            if total_pages > 0:
                boundaries.append(StudentBoundary(
                    student_key="学生A",
                    start_page=0,
                    end_page=total_pages - 1,
                    confidence=0.3,
                    needs_confirmation=True,
                    student_info=StudentInfo(
                        name="学生A",
                        student_id="UNKNOWN_001",
                        confidence=0.3,
                        is_placeholder=True
                    )
                ))
            return boundaries
        
        # 改进的题目循环检测逻辑
        boundary_ranges = []
        current_start = 0
        last_max_question = 0
        question_sequence = []  # 记录题目序列
        page_question_map = {}  # 页面 -> 题目编号的映射
        
        logger.info(f"开始改进的题目循环检测，共 {len(page_analyses)} 页")
        
        # 第一步：提取所有页面的题目信息
        for i, analysis in enumerate(page_analyses):
            # 跳过封面页
            if analysis.is_cover_page:
                continue
            
            # 获取当前页的题目编号
            current_questions = []
            
            # 从 question_numbers 获取
            if analysis.question_numbers:
                for q in analysis.question_numbers:
                    try:
                        q_num = self._normalize_question_number(q)
                        if q_num > 0:  # 过滤无效题号
                            current_questions.append(q_num)
                    except ValueError:
                        continue
            
            # 从 first_question 获取
            if analysis.first_question:
                try:
                    q_num = self._normalize_question_number(analysis.first_question)
                    if q_num > 0 and q_num not in current_questions:
                        current_questions.append(q_num)
                except ValueError:
                    pass
            
            if current_questions:
                page_question_map[i] = sorted(current_questions)
        
        # 第二步：分析题目序列，检测循环
        pages_with_questions = sorted(page_question_map.keys())
        
        for idx, page_idx in enumerate(pages_with_questions):
            current_questions = page_question_map[page_idx]
            min_question = min(current_questions)
            max_question = max(current_questions)
            
            logger.debug(f"页面 {page_idx}: 题目 {current_questions}, min={min_question}, max={max_question}")
            
            # 改进的循环检测逻辑
            is_cycle_start = False
            
            # 条件1：题目编号显著回退（强信号）
            if (min_question <= 2 and  # 回到第1或第2题
                last_max_question >= 5 and  # 之前已经到了第5题或更后
                page_idx > current_start + 2):  # 确保不是刚开始
                is_cycle_start = True
                logger.info(f"检测到强循环信号：页面 {page_idx}，题目从 {last_max_question} 回到 {min_question}")
            
            # 条件2：题目编号中等回退 + 连续性中断（中等信号）
            elif (min_question <= 3 and
                  last_max_question >= 8 and
                  page_idx > current_start + 3):
                # 检查是否有连续性中断
                if idx > 0:
                    prev_page = pages_with_questions[idx - 1]
                    prev_questions = page_question_map[prev_page]
                    prev_max = max(prev_questions)
                    
                    # 如果前一页的最大题号远大于当前页的最小题号
                    if prev_max - min_question >= 5:
                        is_cycle_start = True
                        logger.info(f"检测到中等循环信号：页面 {page_idx}，题目从 {prev_max} 跳到 {min_question}")
            
            # 条件3：题目密度突变（弱信号，需要结合其他条件）
            elif (min_question == 1 and
                  last_max_question >= 10 and
                  page_idx > current_start + 5):
                # 检查题目密度是否突然增加（可能是新学生的开始）
                if idx > 0:
                    prev_page = pages_with_questions[idx - 1]
                    prev_questions = page_question_map[prev_page]
                    
                    # 当前页题目数量明显多于前一页
                    if len(current_questions) >= len(prev_questions) * 1.5:
                        is_cycle_start = True
                        logger.info(f"检测到弱循环信号：页面 {page_idx}，题目密度突变")
            
            if is_cycle_start:
                # 发现新学生的开始
                if page_idx > current_start:
                    boundary_ranges.append((current_start, page_idx - 1))
                current_start = page_idx
                last_max_question = max_question
                question_sequence = [min_question]
            else:
                # 更新最大题号
                last_max_question = max(last_max_question, max_question)
                question_sequence.append(min_question)
        
        # 添加最后一个学生的范围
        if current_start < len(page_analyses):
            boundary_ranges.append((current_start, len(page_analyses) - 1))
        
        # 第三步：如果没有检测到任何边界，使用智能估算
        if not boundary_ranges or len(boundary_ranges) == 1:
            # 分析题目分布，估算学生数量
            all_questions = []
            for questions in page_question_map.values():
                all_questions.extend(questions)
            
            if all_questions:
                max_q = max(all_questions)
                min_q = min(all_questions)
                question_range = max_q - min_q + 1
                
                # 如果题目范围较大，可能有多个学生
                if question_range >= 15 and total_pages >= 30:
                    # 估算：假设每个学生大约15-25页
                    estimated_pages_per_student = 20
                    estimated_students = max(1, total_pages // estimated_pages_per_student)
                    
                    if estimated_students > 1:
                        boundary_ranges = []
                        pages_per_student = total_pages // estimated_students
                        for i in range(estimated_students):
                            start = i * pages_per_student
                            end = min((i + 1) * pages_per_student - 1, total_pages - 1)
                            if i == estimated_students - 1:  # 最后一个学生包含剩余页面
                                end = total_pages - 1
                            boundary_ranges.append((start, end))
                        
                        logger.info(f"基于题目分布和页数估算检测到 {estimated_students} 个学生")
                else:
                    # 题目范围较小或页数较少，可能只有一个学生
                    boundary_ranges = [(0, total_pages - 1)]
                    logger.info("题目分布表明可能只有一个学生")
            else:
                # 没有题目信息，默认单个学生
                boundary_ranges = [(0, total_pages - 1)]
        
        logger.info(f"最终检测到 {len(boundary_ranges)} 个学生边界: {boundary_ranges}")
        
        # 第四步：转换为 StudentBoundary 对象
        for idx, (start, end) in enumerate(boundary_ranges):
            student_count = idx + 1
            
            # 根据检测方法和边界数量计算置信度
            if len(boundary_ranges) == 1:
                # 单个学生，置信度较低
                confidence = 0.5
            elif len(boundary_ranges) <= 3:
                # 2-3个学生，置信度中等
                confidence = 0.7
            else:
                # 多个学生，置信度较高
                confidence = 0.75
            
            # 使用唯一的学生标识（包含索引）
            student_key = f"学生{chr(65 + idx)}"  # 学生A, 学生B, 学生C...
            student_id = f"STUDENT_{student_count:03d}"  # STUDENT_001, STUDENT_002...
            
            boundaries.append(StudentBoundary(
                student_key=student_key,
                start_page=start,
                end_page=end,
                confidence=confidence,
                needs_confirmation=confidence < 0.8,
                student_info=StudentInfo(
                    name=student_key,
                    student_id=student_id,
                    confidence=confidence,
                    is_placeholder=True
                )
            ))
        
        return boundaries
    
    def _normalize_question_number(self, q: str) -> int:
        """将题目编号标准化为数字"""
        if not q:
            return 0
        
        # 移除常见前缀和后缀
        q = str(q).lower().strip()
        
        # 移除括号内容，如 "7(a)" -> "7", "15(1)" -> "15"
        import re
        q = re.sub(r'\([^)]*\)', '', q)
        q = re.sub(r'\[[^\]]*\]', '', q)  # 移除方括号
        
        # 移除常见前缀
        for prefix in ['question', 'q', '第', '题', 'no.', 'no', '#', '.']:
            q = q.replace(prefix, '')
        q = q.strip('.,;: ')
        
        # 中文数字转换
        chinese_nums = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
            '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20
        }
        if q in chinese_nums:
            return chinese_nums[q]
        
        # 提取数字部分
        numbers = re.findall(r'\d+', q)
        if numbers:
            return int(numbers[0])
        
        # 如果都失败了，返回0
        return 0
    
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
    
    def get_confidence_analysis(
        self,
        boundary: StudentBoundary,
        student_markers: Dict[int, Optional[StudentInfo]],
        page_analyses: List[PageAnalysis]
    ) -> Dict[str, Any]:
        """
        获取边界置信度的详细分析
        
        用于解释为什么某个边界需要人工确认，提供可操作的反馈。
        
        Args:
            boundary: 学生边界
            student_markers: 学生标识信息
            page_analyses: 页面分析结果
            
        Returns:
            Dict[str, Any]: 置信度分析结果，包含各项得分和建议
        """
        # 计算各项得分
        student_info_score = 0.0
        if boundary.student_info and not boundary.student_info.is_placeholder:
            student_info_score = boundary.student_info.confidence
        
        question_continuity = self._calculate_question_continuity(boundary, page_analyses)
        boundary_clarity = self._calculate_boundary_clarity(boundary, student_markers)
        
        # 生成分析报告
        analysis = {
            "overall_confidence": boundary.confidence,
            "needs_confirmation": boundary.needs_confirmation,
            "threshold": self.confidence_threshold,
            "factors": {
                "student_info": {
                    "score": student_info_score,
                    "weight": 1.0,
                    "description": "学生标识信息的置信度"
                },
                "question_continuity": {
                    "score": question_continuity,
                    "weight": 1.0,
                    "description": "题目序列的连续性"
                },
                "boundary_clarity": {
                    "score": boundary_clarity,
                    "weight": 1.0,
                    "description": "边界的清晰度"
                }
            },
            "issues": [],
            "recommendations": []
        }
        
        # 识别问题
        if student_info_score < 0.6:
            analysis["issues"].append("学生标识信息缺失或置信度较低")
            analysis["recommendations"].append("建议人工确认学生身份")
        
        if question_continuity < 0.5:
            analysis["issues"].append("题目序列不连续，可能存在跨页或缺页")
            analysis["recommendations"].append("检查是否有题目跨页或页面缺失")
        
        if boundary_clarity < 0.7:
            analysis["issues"].append("边界不够清晰，可能存在学生切换误判")
            analysis["recommendations"].append("确认学生边界位置是否正确")
        
        # 如果没有问题
        if not analysis["issues"]:
            analysis["issues"].append("无明显问题")
            analysis["recommendations"].append("置信度较高，可以直接使用")
        
        return analysis
    
    def aggregate_student_results(
        self,
        boundaries: List[StudentBoundary],
        grading_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        聚合学生结果
        
        为每个学生聚合其范围内的所有题目结果，正确处理跨页题目避免重复计算。
        
        Args:
            boundaries: 学生边界列表
            grading_results: 批改结果列表（按页面索引排序）
            
        Returns:
            List[Dict[str, Any]]: 每个学生的聚合结果
        """
        student_results = []
        
        logger.info(f"开始聚合学生结果，共 {len(boundaries)} 个学生")
        
        for boundary in boundaries:
            logger.info(
                f"聚合学生 {boundary.student_key}，"
                f"页面范围 [{boundary.start_page}, {boundary.end_page}]"
            )
            
            # 提取该学生范围内的所有批改结果
            student_pages = []
            for page_idx in range(boundary.start_page, boundary.end_page + 1):
                if page_idx < len(grading_results):
                    student_pages.append(grading_results[page_idx])
            
            # 聚合题目结果
            aggregated_questions = self._aggregate_questions(student_pages)
            
            # 计算总分
            total_score = sum(q.get("score", 0.0) for q in aggregated_questions)
            max_total_score = sum(q.get("max_score", 0.0) for q in aggregated_questions)
            
            # 构建学生结果
            student_result = {
                "student_key": boundary.student_key,
                "student_id": boundary.student_info.student_id if boundary.student_info else None,
                "student_name": boundary.student_info.name if boundary.student_info else None,
                "start_page": boundary.start_page,
                "end_page": boundary.end_page,
                "total_score": total_score,
                "max_total_score": max_total_score,
                "question_results": aggregated_questions,
                "confidence": boundary.confidence,
                "needs_confirmation": boundary.needs_confirmation,
                "detection_method": boundary.detection_method,
                "page_count": boundary.end_page - boundary.start_page + 1
            }
            
            student_results.append(student_result)
            
            logger.info(
                f"学生 {boundary.student_key} 聚合完成：{len(aggregated_questions)} 道题，"
                f"总分 {total_score}/{max_total_score}"
            )
        
        return student_results
    
    def _aggregate_questions(
        self,
        student_pages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        聚合学生页面中的题目结果，处理跨页题目避免重复计算
        
        Args:
            student_pages: 学生的所有页面批改结果
            
        Returns:
            List[Dict[str, Any]]: 聚合后的题目结果列表
        """
        # 使用字典存储题目结果，key 为题目编号
        question_map = {}
        
        for page in student_pages:
            # 从不同字段提取题目结果
            page_questions = self._extract_questions_from_page(page)
            
            for question in page_questions:
                question_id = question.get("question_id")
                if not question_id:
                    continue
                
                # 检查是否是跨页题目
                is_cross_page = question.get("is_cross_page", False)
                
                if question_id in question_map:
                    # 题目已存在，需要合并
                    existing = question_map[question_id]
                    
                    # 如果是跨页题目，合并结果
                    if is_cross_page or existing.get("is_cross_page", False):
                        merged = self._merge_cross_page_question(existing, question)
                        question_map[question_id] = merged
                        logger.debug(f"合并跨页题目 {question_id}")
                    else:
                        # 不是跨页题目但重复出现，选择置信度更高的
                        existing_conf = existing.get("confidence", 0.0)
                        new_conf = question.get("confidence", 0.0)
                        
                        if new_conf > existing_conf:
                            question_map[question_id] = question
                            logger.debug(
                                f"题目 {question_id} 重复，选择置信度更高的结果 "
                                f"({new_conf} > {existing_conf})"
                            )
                else:
                    # 新题目，直接添加
                    question_map[question_id] = question
        
        # 转换为列表并排序
        aggregated = list(question_map.values())
        
        # 按题目编号排序
        def sort_key(q):
            qid = q.get("question_id", "")
            try:
                return self._normalize_question_number(str(qid))
            except ValueError:
                return 999  # 无法解析的题号放在最后
        
        aggregated.sort(key=sort_key)
        
        return aggregated
    
    def _extract_questions_from_page(
        self,
        page: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        从页面批改结果中提取题目结果
        
        支持多种数据格式：
        - question_results 字段（列表）
        - questions 字段（列表）
        - 单个题目（question_id 字段）
        
        Args:
            page: 页面批改结果
            
        Returns:
            List[Dict[str, Any]]: 题目结果列表
        """
        questions = []
        
        # 方法1：从 question_results 字段提取
        if "question_results" in page:
            qr = page["question_results"]
            if isinstance(qr, list):
                questions.extend(qr)
            elif isinstance(qr, dict):
                questions.append(qr)
        
        # 方法2：从 questions 字段提取
        if "questions" in page:
            qs = page["questions"]
            if isinstance(qs, list):
                questions.extend(qs)
            elif isinstance(qs, dict):
                questions.append(qs)
        
        # 方法3：页面本身就是一个题目结果
        if "question_id" in page and not questions:
            questions.append(page)
        
        # 方法4：从 metadata 中提取
        if "metadata" in page and not questions:
            metadata = page["metadata"]
            if isinstance(metadata, dict) and "questions" in metadata:
                qs = metadata["questions"]
                if isinstance(qs, list):
                    questions.extend(qs)
        
        return questions
    
    def _merge_cross_page_question(
        self,
        existing: Dict[str, Any],
        new: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        合并跨页题目的结果
        
        合并规则：
        1. 满分只计算一次（取较大值）
        2. 得分累加（如果有多个得分点）
        3. 反馈合并
        4. 置信度取平均
        5. 页面索引合并
        
        Args:
            existing: 已存在的题目结果
            new: 新的题目结果
            
        Returns:
            Dict[str, Any]: 合并后的题目结果
        """
        merged = existing.copy()
        
        # 1. 满分只计算一次（取较大值）
        existing_max = existing.get("max_score", 0.0)
        new_max = new.get("max_score", 0.0)
        merged["max_score"] = max(existing_max, new_max)
        
        # 2. 得分处理：如果有得分点明细，合并得分点；否则取较大值
        if "scoring_point_results" in existing or "scoring_point_results" in new:
            # 合并得分点
            existing_points = existing.get("scoring_point_results", [])
            new_points = new.get("scoring_point_results", [])
            
            # 使用字典去重合并
            point_map = {}
            for point in existing_points:
                point_desc = point.get("description", "")
                point_map[point_desc] = point
            
            for point in new_points:
                point_desc = point.get("description", "")
                if point_desc not in point_map:
                    point_map[point_desc] = point
            
            merged["scoring_point_results"] = list(point_map.values())
            
            # 重新计算总得分
            merged["score"] = sum(
                p.get("awarded", 0.0) for p in merged["scoring_point_results"]
            )
        else:
            # 没有得分点明细，取较大的得分
            existing_score = existing.get("score", 0.0)
            new_score = new.get("score", 0.0)
            merged["score"] = max(existing_score, new_score)
        
        # 3. 反馈合并
        existing_feedback = existing.get("feedback", "")
        new_feedback = new.get("feedback", "")
        
        if existing_feedback and new_feedback:
            # 如果两个反馈不同，合并它们
            if existing_feedback != new_feedback:
                merged["feedback"] = f"{existing_feedback}\n\n{new_feedback}"
            else:
                merged["feedback"] = existing_feedback
        elif new_feedback:
            merged["feedback"] = new_feedback
        
        # 4. 置信度取平均
        existing_conf = existing.get("confidence", 0.0)
        new_conf = new.get("confidence", 0.0)
        merged["confidence"] = (existing_conf + new_conf) / 2
        
        # 5. 页面索引合并
        existing_pages = existing.get("page_indices", [])
        new_pages = new.get("page_indices", [])
        
        if not isinstance(existing_pages, list):
            existing_pages = [existing_pages] if existing_pages is not None else []
        if not isinstance(new_pages, list):
            new_pages = [new_pages] if new_pages is not None else []
        
        merged["page_indices"] = sorted(set(existing_pages + new_pages))
        
        # 6. 标记为跨页题目
        merged["is_cross_page"] = True
        
        # 7. 记录合并来源
        existing_sources = existing.get("merge_source", [])
        new_sources = new.get("merge_source", [])
        
        if not isinstance(existing_sources, list):
            existing_sources = [existing_sources] if existing_sources else []
        if not isinstance(new_sources, list):
            new_sources = [new_sources] if new_sources else []
        
        merged["merge_source"] = existing_sources + new_sources + ["cross_page_merge"]
        
        return merged
