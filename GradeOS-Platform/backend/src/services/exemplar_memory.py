"""
判例记忆服务

提供判例的存储、检索和淘汰功能，支持向量相似度搜索。
验证：需求 4.1, 4.2, 4.3, 4.4, 4.5
"""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4

import asyncpg

from src.config.llm import get_llm_config
from src.services.llm_client import UnifiedLLMClient, get_llm_client

from src.models.exemplar import Exemplar, ExemplarCreateRequest
from src.utils.pool_manager import UnifiedPoolManager


logger = logging.getLogger(__name__)


class OpenRouterEmbeddings:
    """Thin async embedding wrapper for OpenRouter."""

    def __init__(
        self,
        *,
        client: Optional[UnifiedLLMClient] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        config = get_llm_config()
        resolved_model = model or config.get_model("embedding")
        if not resolved_model:
            raise ValueError("Embedding model is not configured")
        self.client = client or get_llm_client()
        self.model = resolved_model
        self.api_key = api_key

    async def aembed_query(self, text: str) -> List[float]:
        embeddings = await self.client.embed(
            inputs=text,
            model=self.model,
            api_key_override=self.api_key,
        )
        return embeddings[0] if embeddings else []


class ExemplarMemory:
    """
    判例记忆库
    
    存储和检索老师确认的正确批改示例，用于 few-shot 学习。
    使用 pgvector 进行向量相似度搜索。
    
    验证：需求 4.1, 4.2, 4.3, 4.4, 4.5
    """
    
    def __init__(
        self,
        pool_manager: Optional[UnifiedPoolManager] = None,
        embedding_model: Optional[OpenRouterEmbeddings] = None
    ):
        """
        初始化判例记忆服务
        
        Args:
            pool_manager: 数据库连接池管理器
            embedding_model: 向量嵌入模型（可选，如果不提供则在需要时创建）
        """
        self.pool_manager = pool_manager or UnifiedPoolManager()
        self.embedding_model = embedding_model
        if self.embedding_model is None:
            try:
                self.embedding_model = OpenRouterEmbeddings()
            except Exception as e:
                logger.warning(f"embedding model unavailable: {e}")
                self.embedding_model = None
        
        logger.info("ExemplarMemory 服务初始化完成")
    
    async def store_exemplar(
        self,
        grading_result: Dict[str, Any],
        teacher_id: str,
        teacher_feedback: str
    ) -> str:
        """
        存储老师确认的判例
        
        验证：需求 4.1, 4.2
        属性 8：判例存储完整性
        
        Args:
            grading_result: 批改结果字典，包含 question_type, question_image_hash, 
                          student_answer_text, score, max_score
            teacher_id: 确认教师ID
            teacher_feedback: 教师评语
        
        Returns:
            exemplar_id: 判例唯一标识
        
        Raises:
            ValueError: 如果必需字段缺失
            Exception: 数据库操作失败
        """
        try:
            # 验证必需字段
            required_fields = [
                'question_type', 'question_image_hash', 
                'student_answer_text', 'score', 'max_score'
            ]
            for field in required_fields:
                if field not in grading_result:
                    raise ValueError(f"缺少必需字段: {field}")
            
            # 生成向量嵌入
            # 组合题目类型、学生答案和评语作为嵌入输入
            embedding_text = f"{grading_result['question_type']}: {grading_result['student_answer_text']} | {teacher_feedback}"
            
            if self.embedding_model:
                embedding = await self.embedding_model.aembed_query(embedding_text)
                # 将向量转换为 pgvector 格式的字符串
                embedding_str = f"[{','.join(map(str, embedding))}]"
            else:
                # 如果没有 embedding 模型，使用 NULL
                logger.warning("embedding 模型未初始化，将使用 NULL 向量")
                embedding_str = None
            
            # 生成唯一ID
            exemplar_id = str(uuid4())
            
            # 存储到数据库
            async with self.pool_manager.pg_connection() as conn:
                if embedding_str:
                    await conn.execute(
                        """
                        INSERT INTO exemplars (
                            exemplar_id, question_type, question_image_hash,
                            student_answer_text, score, max_score,
                            teacher_feedback, teacher_id, confirmed_at,
                            usage_count, embedding
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::vector)
                        """,
                        exemplar_id,
                        grading_result['question_type'],
                        grading_result['question_image_hash'],
                        grading_result['student_answer_text'],
                        float(grading_result['score']),
                        float(grading_result['max_score']),
                        teacher_feedback,
                        teacher_id,
                        datetime.now(),
                        0,
                        embedding_str
                    )
                else:
                    # 没有 embedding，不插入 embedding 字段
                    await conn.execute(
                        """
                        INSERT INTO exemplars (
                            exemplar_id, question_type, question_image_hash,
                            student_answer_text, score, max_score,
                            teacher_feedback, teacher_id, confirmed_at,
                            usage_count
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        exemplar_id,
                        grading_result['question_type'],
                        grading_result['question_image_hash'],
                        grading_result['student_answer_text'],
                        float(grading_result['score']),
                        float(grading_result['max_score']),
                        teacher_feedback,
                        teacher_id,
                        datetime.now(),
                        0
                    )
            
            logger.info(f"成功存储判例: {exemplar_id}")
            return exemplar_id
            
        except ValueError as e:
            logger.error(f"判例数据验证失败: {e}")
            raise
        except Exception as e:
            logger.error(f"存储判例失败: {e}")
            raise
    
    async def retrieve_similar(
        self,
        question_image_hash: str,
        question_type: str,
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[Exemplar]:
        """
        检索最相似的判例
        
        验证：需求 4.3, 4.4
        属性 9：判例检索数量约束
        
        Args:
            question_image_hash: 题目图片哈希值
            question_type: 题目类型
            top_k: 返回数量（3-5个）
            min_similarity: 最小相似度阈值（>= 0.7）
        
        Returns:
            判例列表，按相似度降序排列
        """
        try:
            # 限制返回数量在合理范围内
            top_k = min(max(top_k, 1), 5)
            
            # 如果没有 embedding 模型，返回空列表
            if not self.embedding_model:
                logger.warning("embedding 模型未初始化，无法检索判例")
                return []
            
            # 生成查询向量
            query_text = f"{question_type}: {question_image_hash}"
            query_embedding = await self.embedding_model.aembed_query(query_text)
            query_embedding_str = f"[{','.join(map(str, query_embedding))}]"
            
            # 使用余弦相似度检索
            # 注意：pgvector 的余弦距离范围是 [0, 2]，0 表示完全相同
            # 相似度 = 1 - (距离 / 2)
            async with self.pool_manager.pg_connection() as conn:
                rows = await conn.fetch(
                    """
                    SELECT 
                        exemplar_id, question_type, question_image_hash,
                        student_answer_text, score, max_score,
                        teacher_feedback, teacher_id, confirmed_at,
                        usage_count,
                        1 - (embedding <=> $1::vector) / 2 AS similarity
                    FROM exemplars
                    WHERE question_type = $2
                        AND embedding IS NOT NULL
                        AND 1 - (embedding <=> $1::vector) / 2 >= $3
                    ORDER BY embedding <=> $1::vector
                    LIMIT $4
                    """,
                    query_embedding_str,
                    question_type,
                    min_similarity,
                    top_k
                )
            
            # 转换为 Exemplar 对象
            exemplars = []
            for row in rows:
                exemplar = Exemplar(
                    exemplar_id=str(row['exemplar_id']),
                    question_type=row['question_type'],
                    question_image_hash=row['question_image_hash'],
                    student_answer_text=row['student_answer_text'],
                    score=float(row['score']),
                    max_score=float(row['max_score']),
                    teacher_feedback=row['teacher_feedback'],
                    teacher_id=str(row['teacher_id']),
                    confirmed_at=row['confirmed_at'],
                    usage_count=row['usage_count'],
                    embedding=None  # 不返回向量以节省内存
                )
                exemplars.append(exemplar)
                
                # 更新使用次数
                await self._increment_usage_count(str(row['exemplar_id']))
            
            logger.info(f"检索到 {len(exemplars)} 个相似判例")
            return exemplars
            
        except Exception as e:
            logger.error(f"检索判例失败: {e}")
            # 降级：返回空列表而不抛出异常
            return []
    
    async def _increment_usage_count(self, exemplar_id: str) -> None:
        """增加判例使用次数"""
        try:
            async with self.pool_manager.pg_connection() as conn:
                await conn.execute(
                    """
                    UPDATE exemplars
                    SET usage_count = usage_count + 1
                    WHERE exemplar_id = $1
                    """,
                    exemplar_id
                )
        except Exception as e:
            logger.warning(f"更新判例使用次数失败: {e}")
    
    async def evict_old_exemplars(
        self,
        max_capacity: int,
        retention_days: int = 90
    ) -> int:
        """
        淘汰旧判例
        
        验证：需求 4.5
        属性 10：判例淘汰策略
        
        按使用频率和时效性淘汰旧判例，保持容量在阈值内。
        
        Args:
            max_capacity: 最大容量
            retention_days: 保留天数
        
        Returns:
            淘汰的判例数量
        """
        try:
            async with self.pool_manager.pg_connection() as conn:
                # 统计当前判例数量
                count_row = await conn.fetchrow("SELECT COUNT(*) as count FROM exemplars")
                current_count = count_row['count']
                
                if current_count <= max_capacity:
                    logger.info(f"当前判例数量 {current_count} 未超过容量 {max_capacity}，无需淘汰")
                    return 0
                
                # 计算需要淘汰的数量
                evict_count = current_count - max_capacity
                
                # 淘汰策略：
                # 1. 优先淘汰超过保留期的判例
                # 2. 其次淘汰使用频率最低的判例
                # 3. 最后按确认时间从旧到新淘汰
                deleted_rows = await conn.fetch(
                    """
                    DELETE FROM exemplars
                    WHERE exemplar_id IN (
                        SELECT exemplar_id
                        FROM exemplars
                        ORDER BY 
                            CASE 
                                WHEN confirmed_at < NOW() - INTERVAL '1 day' * $2 THEN 0
                                ELSE 1
                            END,
                            usage_count ASC,
                            confirmed_at ASC
                        LIMIT $1
                    )
                    RETURNING exemplar_id
                    """,
                    evict_count,
                    retention_days
                )
                
                evicted_count = len(deleted_rows)
                logger.info(f"成功淘汰 {evicted_count} 个旧判例")
                return evicted_count
                
        except Exception as e:
            logger.error(f"淘汰判例失败: {e}")
            return 0
    
    async def get_exemplar_by_id(self, exemplar_id: str) -> Optional[Exemplar]:
        """根据ID获取判例"""
        try:
            async with self.pool_manager.pg_connection() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT 
                        exemplar_id, question_type, question_image_hash,
                        student_answer_text, score, max_score,
                        teacher_feedback, teacher_id, confirmed_at,
                        usage_count
                    FROM exemplars
                    WHERE exemplar_id = $1
                    """,
                    exemplar_id
                )
                
                if not row:
                    return None
                
                return Exemplar(
                    exemplar_id=str(row['exemplar_id']),
                    question_type=row['question_type'],
                    question_image_hash=row['question_image_hash'],
                    student_answer_text=row['student_answer_text'],
                    score=float(row['score']),
                    max_score=float(row['max_score']),
                    teacher_feedback=row['teacher_feedback'],
                    teacher_id=str(row['teacher_id']),
                    confirmed_at=row['confirmed_at'],
                    usage_count=row['usage_count'],
                    embedding=None
                )
                
        except Exception as e:
            logger.error(f"获取判例失败: {e}")
            return None
