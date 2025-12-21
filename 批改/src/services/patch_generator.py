"""补丁生成器服务

根据失败模式生成候选规则补丁。
验证：需求 9.2
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from src.models.failure_pattern import FailurePattern, PatternType
from src.models.rule_patch import RulePatch, PatchType


logger = logging.getLogger(__name__)


class PatchGenerator:
    """补丁生成器
    
    功能：
    1. 根据失败模式生成候选补丁（generate_patch）
    
    验证：需求 9.2
    """
    
    def __init__(self, version_prefix: str = "v1"):
        """初始化补丁生成器
        
        Args:
            version_prefix: 版本号前缀
        """
        self.version_prefix = version_prefix
        self._patch_counter = 0
    
    async def generate_patch(
        self,
        pattern: FailurePattern
    ) -> Optional[RulePatch]:
        """根据失败模式生成候选补丁
        
        分析失败模式的特征，生成对应的规则补丁。
        只有可修复的模式才会生成补丁。
        
        验证：需求 9.2
        
        Args:
            pattern: 失败模式
            
        Returns:
            生成的规则补丁，如果模式不可修复则返回 None
        """
        # 检查模式是否可修复
        if not pattern.is_fixable:
            logger.info(f"模式 {pattern.pattern_id} 不可修复，跳过补丁生成")
            return None
        
        logger.info(f"为模式 {pattern.pattern_id} 生成补丁")
        
        # 根据模式类型生成不同的补丁
        if pattern.pattern_type == PatternType.EXTRACTION:
            return await self._generate_extraction_patch(pattern)
        elif pattern.pattern_type == PatternType.NORMALIZATION:
            return await self._generate_normalization_patch(pattern)
        elif pattern.pattern_type == PatternType.MATCHING:
            return await self._generate_matching_patch(pattern)
        elif pattern.pattern_type == PatternType.SCORING:
            return await self._generate_scoring_patch(pattern)
        else:
            logger.warning(f"未知的模式类型：{pattern.pattern_type}")
            return None
    
    async def _generate_extraction_patch(
        self,
        pattern: FailurePattern
    ) -> Optional[RulePatch]:
        """生成提取阶段的补丁
        
        提取阶段的失败通常需要优化提示词。
        
        Args:
            pattern: 失败模式
            
        Returns:
            提示词补丁
        """
        # 生成版本号
        version = self._allocate_version()
        
        # 构建补丁内容
        content = {
            "patch_target": "extraction_prompt",
            "pattern_type": pattern.pattern_type.value,
            "affected_questions": pattern.affected_question_types or [],
            "enhancement": {
                "type": "prompt_optimization",
                "description": "优化答案提取提示词，增强答案区域识别能力",
                "prompt_additions": [
                    "请特别注意答案区域的边界标记",
                    "如果答案包含多个部分，请完整提取所有部分",
                    "对于手写答案，请尽可能准确识别每个字符"
                ]
            },
            "confidence_boost": 0.1  # 预期提升置信度
        }
        
        patch = RulePatch(
            patch_type=PatchType.PROMPT,
            version=version,
            description=f"优化提取提示词：{pattern.description}",
            content=content,
            source_pattern_id=pattern.pattern_id
        )
        
        logger.info(f"生成提取补丁：{patch.patch_id} (版本 {version})")
        return patch
    
    async def _generate_normalization_patch(
        self,
        pattern: FailurePattern
    ) -> Optional[RulePatch]:
        """生成规范化阶段的补丁
        
        规范化阶段的失败通常需要添加新的规范化规则。
        
        Args:
            pattern: 失败模式
            
        Returns:
            规则补丁
        """
        # 生成版本号
        version = self._allocate_version()
        
        # 从模式描述中提取规则信息
        # 例如："规范化规则 'unit_conversion' 应用后仍然匹配失败"
        rule_name = self._extract_rule_name(pattern.description)
        
        # 构建补丁内容
        content = {
            "patch_target": "normalization_rules",
            "pattern_type": pattern.pattern_type.value,
            "rule_name": rule_name or "unknown_rule",
            "enhancement": {
                "type": "rule_extension",
                "description": f"扩展规范化规则以处理更多变体",
                "new_variants": self._suggest_variants(pattern),
                "examples": [
                    {
                        "input": "100cm",
                        "output": "1m",
                        "rule": "unit_conversion"
                    }
                ]
            }
        }
        
        patch = RulePatch(
            patch_type=PatchType.RULE,
            version=version,
            description=f"扩展规范化规则：{pattern.description}",
            content=content,
            source_pattern_id=pattern.pattern_id
        )
        
        logger.info(f"生成规范化补丁：{patch.patch_id} (版本 {version})")
        return patch
    
    async def _generate_matching_patch(
        self,
        pattern: FailurePattern
    ) -> Optional[RulePatch]:
        """生成匹配阶段的补丁
        
        匹配阶段的失败通常需要添加同义词规则或放宽匹配条件。
        
        Args:
            pattern: 失败模式
            
        Returns:
            规则补丁
        """
        # 生成版本号
        version = self._allocate_version()
        
        # 构建补丁内容
        content = {
            "patch_target": "matching_rules",
            "pattern_type": pattern.pattern_type.value,
            "enhancement": {
                "type": "synonym_expansion",
                "description": "添加同义词规则以提高匹配成功率",
                "synonym_groups": self._suggest_synonyms(pattern),
                "fuzzy_threshold": 0.85  # 模糊匹配阈值
            }
        }
        
        patch = RulePatch(
            patch_type=PatchType.RULE,
            version=version,
            description=f"扩展匹配规则：{pattern.description}",
            content=content,
            source_pattern_id=pattern.pattern_id
        )
        
        logger.info(f"生成匹配补丁：{patch.patch_id} (版本 {version})")
        return patch
    
    async def _generate_scoring_patch(
        self,
        pattern: FailurePattern
    ) -> Optional[RulePatch]:
        """生成评分阶段的补丁
        
        评分阶段的失败通常需要调整评分规则或校准配置。
        注意：大多数评分失败不适合自动修复，需要人工介入。
        
        Args:
            pattern: 失败模式
            
        Returns:
            规则补丁或 None
        """
        # 检查是否是可以自动修复的评分问题
        if "固定扣分" not in pattern.description and "扣分规则" not in pattern.description:
            logger.info(f"评分模式 {pattern.pattern_id} 需要人工介入，不生成补丁")
            return None
        
        # 生成版本号
        version = self._allocate_version()
        
        # 构建补丁内容
        content = {
            "patch_target": "scoring_rules",
            "pattern_type": pattern.pattern_type.value,
            "enhancement": {
                "type": "scoring_adjustment",
                "description": "调整评分规则以减少评分偏差",
                "adjustments": [
                    {
                        "condition": "部分正确",
                        "old_deduction": 5.0,
                        "new_deduction": 3.0,
                        "reason": "根据教师反馈调整扣分力度"
                    }
                ]
            }
        }
        
        patch = RulePatch(
            patch_type=PatchType.RULE,
            version=version,
            description=f"调整评分规则：{pattern.description}",
            content=content,
            source_pattern_id=pattern.pattern_id
        )
        
        logger.info(f"生成评分补丁：{patch.patch_id} (版本 {version})")
        return patch
    
    def _allocate_version(self) -> str:
        """分配版本号
        
        Returns:
            版本号字符串，格式：v1.0.1
        """
        self._patch_counter += 1
        return f"{self.version_prefix}.0.{self._patch_counter}"
    
    def _extract_rule_name(self, description: str) -> Optional[str]:
        """从描述中提取规则名称
        
        Args:
            description: 模式描述
            
        Returns:
            规则名称或 None
        """
        # 简单的模式匹配：查找单引号之间的内容
        import re
        match = re.search(r"'([^']+)'", description)
        if match:
            return match.group(1)
        return None
    
    def _suggest_variants(self, pattern: FailurePattern) -> List[str]:
        """建议规范化变体
        
        Args:
            pattern: 失败模式
            
        Returns:
            变体列表
        """
        # 根据模式特征建议变体
        # 这里返回一些通用的变体建议
        variants = [
            "大小写变体",
            "空格变体",
            "标点符号变体",
            "单位变体"
        ]
        
        # 如果有错误签名，可以根据签名生成更具体的变体
        if pattern.error_signature:
            if "unit" in pattern.error_signature.lower():
                variants.extend(["cm->m", "mm->cm", "kg->g"])
            elif "case" in pattern.error_signature.lower():
                variants.extend(["大写->小写", "首字母大写"])
        
        return variants
    
    def _suggest_synonyms(self, pattern: FailurePattern) -> List[Dict[str, List[str]]]:
        """建议同义词组
        
        Args:
            pattern: 失败模式
            
        Returns:
            同义词组列表
        """
        # 根据模式特征建议同义词
        synonym_groups = [
            {
                "canonical": "正确",
                "synonyms": ["对", "是", "√", "✓", "yes"]
            },
            {
                "canonical": "错误",
                "synonyms": ["错", "否", "×", "✗", "no"]
            }
        ]
        
        # 如果有建议的修复方案，可以从中提取同义词
        if pattern.suggested_fix and "同义词" in pattern.suggested_fix:
            # 这里可以添加更智能的同义词提取逻辑
            pass
        
        return synonym_groups


# 全局单例
_patch_generator: Optional[PatchGenerator] = None


def get_patch_generator() -> PatchGenerator:
    """获取补丁生成器单例"""
    global _patch_generator
    if _patch_generator is None:
        _patch_generator = PatchGenerator()
    return _patch_generator
