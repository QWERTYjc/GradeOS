"""
测试部署模式检测和数据库降级逻辑

验证：需求 11.1, 11.6, 11.7, 11.8
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from src.config.deployment_mode import (
    DeploymentMode,
    DeploymentConfig,
    get_deployment_mode,
    reset_deployment_mode,
)


class TestDeploymentModeDetection:
    """测试部署模式检测"""
    
    def setup_method(self):
        """每个测试前重置"""
        reset_deployment_mode()
    
    def test_no_database_mode_when_database_url_empty(self):
        """
        测试：DATABASE_URL 为空时检测为无数据库模式
        
        验证：需求 11.1, 11.8
        """
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=True):
            reset_deployment_mode()
            config = get_deployment_mode()
            
            assert config.mode == DeploymentMode.NO_DATABASE
            assert config.is_no_database_mode
            assert not config.is_database_mode
            assert config.database_url is None
    
    def test_no_database_mode_when_database_url_not_set(self):
        """
        测试：DATABASE_URL 未设置时检测为无数据库模式
        
        验证：需求 11.1, 11.8
        """
        with patch.dict(os.environ, {}, clear=True):
            reset_deployment_mode()
            config = get_deployment_mode()
            
            assert config.mode == DeploymentMode.NO_DATABASE
            assert config.is_no_database_mode
    
    def test_database_mode_when_database_url_set(self):
        """
        测试：DATABASE_URL 已设置时检测为数据库模式
        
        验证：需求 11.1, 11.8
        """
        test_url = "postgresql://user:pass@localhost:5432/testdb"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}):
            reset_deployment_mode()
            config = get_deployment_mode()
            
            assert config.mode == DeploymentMode.DATABASE
            assert config.is_database_mode
            assert not config.is_no_database_mode
            assert config.database_url == test_url
    
    def test_feature_availability_database_mode(self):
        """
        测试：数据库模式的功能可用性
        
        验证：需求 11.1
        """
        test_url = "postgresql://user:pass@localhost:5432/testdb"
        redis_url = "redis://localhost:6379"
        with patch.dict(os.environ, {
            "DATABASE_URL": test_url,
            "REDIS_URL": redis_url
        }):
            reset_deployment_mode()
            config = get_deployment_mode()
            features = config.get_feature_availability()
            
            assert features["grading"] is True
            assert features["persistence"] is True
            assert features["history"] is True
            assert features["analytics"] is True
            assert features["caching"] is True
            assert features["websocket"] is True
            assert features["mode"] == "database"
    
    def test_feature_availability_no_database_mode(self):
        """
        测试：无数据库模式的功能可用性
        
        验证：需求 11.1, 11.8
        """
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=True):
            reset_deployment_mode()
            config = get_deployment_mode()
            features = config.get_feature_availability()
            
            assert features["grading"] is True
            assert features["persistence"] is False
            assert features["history"] is False
            assert features["analytics"] is False
            assert features["caching"] is True  # 内存缓存
            assert features["websocket"] is False
            assert features["mode"] == "no_database"
    
    def test_connection_string_masking(self):
        """测试连接字符串遮蔽"""
        test_url = "postgresql://user:password@localhost:5432/testdb"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}):
            reset_deployment_mode()
            config = get_deployment_mode()
            
            # 遮蔽后的字符串不应包含密码
            masked = config._mask_connection_string(test_url)
            assert "password" not in masked
            assert "***" in masked
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        config1 = get_deployment_mode()
        config2 = get_deployment_mode()
        
        assert config1 is config2


class TestDatabaseDegradation:
    """测试数据库降级逻辑"""
    
    @pytest.mark.asyncio
    async def test_database_degradation_on_connection_failure(self):
        """
        测试：数据库连接失败时自动降级
        
        验证：需求 11.6, 11.7
        """
        from src.utils.database import Database, DatabaseConfig
        
        # 使用无效的连接字符串
        config = DatabaseConfig()
        config._connection_string = "postgresql://invalid:invalid@invalid:9999/invalid"
        
        db = Database(config)
        
        # 尝试连接（应该失败并降级）
        await db.connect(use_unified_pool=False)
        
        # 验证降级状态
        assert db.is_degraded
        assert not db.is_available
    
    @pytest.mark.asyncio
    async def test_database_connection_raises_error_in_degraded_mode(self):
        """
        测试：降级模式下获取连接应抛出异常
        
        验证：需求 11.7
        """
        from src.utils.database import Database, DatabaseConfig
        
        config = DatabaseConfig()
        config._connection_string = "postgresql://invalid:invalid@invalid:9999/invalid"
        
        db = Database(config)
        await db.connect(use_unified_pool=False)
        
        # 降级模式下获取连接应抛出异常
        with pytest.raises(RuntimeError, match="数据库不可用"):
            async with db.connection() as conn:
                pass
    
    @pytest.mark.asyncio
    async def test_no_database_mode_skips_connection(self):
        """
        测试：无数据库模式跳过数据库连接
        
        验证：需求 11.8
        """
        from src.utils.database import Database, DatabaseConfig
        
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=True):
            reset_deployment_mode()
            
            db = Database()
            await db.connect()
            
            # 应该直接进入降级模式
            assert db.is_degraded
            assert not db.is_available


class TestRubricRegistryNoDatabase:
    """测试 RubricRegistry 在无数据库模式下的行为"""
    
    def test_rubric_registry_works_in_no_database_mode(self):
        """
        测试：RubricRegistry 在无数据库模式下正常工作
        
        验证：需求 11.3
        """
        from src.services.rubric_registry import RubricRegistry, get_global_registry
        from src.models.grading_models import QuestionRubric, ScoringPoint
        
        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=True):
            reset_deployment_mode()
            
            # 创建注册中心
            registry = RubricRegistry()
            
            # 注册评分标准
            rubric = QuestionRubric(
                question_id="1",
                max_score=10.0,
                question_text="测试题目",
                standard_answer="测试答案",
                scoring_points=[
                    ScoringPoint(description="得分点1", score=5.0, is_required=True),
                    ScoringPoint(description="得分点2", score=5.0, is_required=True),
                ],
                alternative_solutions=[],
                grading_notes=""
            )
            registry.register_rubric(rubric)
            
            # 查询评分标准
            result = registry.get_rubric_for_question("1")
            
            assert result.rubric is not None
            assert result.rubric.question_id == "1"
            assert result.rubric.max_score == 10.0
            assert not result.is_default
            assert result.confidence == 1.0
    
    def test_global_registry_singleton(self):
        """测试全局注册中心单例"""
        from src.services.rubric_registry import get_global_registry, reset_global_registry
        
        reset_global_registry()
        
        registry1 = get_global_registry()
        registry2 = get_global_registry()
        
        assert registry1 is registry2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
