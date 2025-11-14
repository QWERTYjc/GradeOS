#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LangGraph Agents - 深度协作多模态架构
已移除OCR依赖，使用纯多模态LLM Vision能力
"""

from .upload_validator import UploadValidator
from .rubric_interpreter import RubricInterpreter
from .scoring_agent import ScoringAgent
from .annotation_builder import AnnotationBuilder
from .knowledge_miner import KnowledgeMiner
from .result_assembler import ResultAssembler

# 🆕 深度协作架构Agent
from .orchestrator_agent import OrchestratorAgent
from .student_detection_agent import StudentDetectionAgent
from .batch_planning_agent import BatchPlanningAgent
from .rubric_master_agent import RubricMasterAgent
from .question_context_agent import QuestionContextAgent
from .grading_worker_agent import GradingWorkerAgent
from .result_aggregator_agent import ResultAggregatorAgent
from .class_analysis_agent import ClassAnalysisAgent

__all__ = [
    'UploadValidator',
    # 'OCRVisionAgent',  # ❗ 已删除 - 系统已迁移至多模态LLM Vision
    'RubricInterpreter',
    'ScoringAgent',
    'AnnotationBuilder',
    'KnowledgeMiner',
    'ResultAssembler',
    # 深度协作架构
    'OrchestratorAgent',
    'StudentDetectionAgent',
    'BatchPlanningAgent',
    'RubricMasterAgent',
    'QuestionContextAgent',
    'GradingWorkerAgent',
    'ResultAggregatorAgent',
    'ClassAnalysisAgent',
]
