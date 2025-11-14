#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地运行器 - 用于本地开发和测试
确保所有依赖正确加载，使用SQLite数据库
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
from dotenv import load_dotenv

# 加载本地环境变量
env_file = project_root / '.env.local'
if env_file.exists():
    load_dotenv(env_file)
    print(f"✓ 已加载本地配置: {env_file}")
else:
    print(f"⚠ 本地配置文件不存在: {env_file}")
    print("使用默认配置...")

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/local_run.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def init_local_database():
    """初始化本地SQLite数据库"""
    logger.info("初始化本地数据库...")
    
    try:
        from functions.database.models import Base
        from sqlalchemy import create_engine
        
        database_url = os.getenv('DATABASE_URL', 'sqlite:///ai_correction.db')
        logger.info(f"数据库URL: {database_url}")
        
        engine = create_engine(database_url)
        Base.metadata.create_all(engine)
        
        logger.info("✓ 数据库初始化成功")
        return True
    except Exception as e:
        logger.error(f"✗ 数据库初始化失败: {e}")
        return False


def test_workflow():
    """测试工作流是否正常运行"""
    logger.info("测试工作流...")
    
    try:
        from functions.langgraph.workflow_new import get_production_workflow
        from functions.langgraph.checkpointer import get_checkpointer
        
        # 获取workflow
        workflow = get_production_workflow()
        logger.info("✓ 工作流加载成功")
        
        # 测试checkpointer
        checkpointer = get_checkpointer('development')
        logger.info(f"✓ Checkpointer初始化成功: {type(checkpointer).__name__}")
        
        return True
    except Exception as e:
        logger.error(f"✗ 工作流测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_test_grading():
    """运行测试批改任务"""
    logger.info("=" * 60)
    logger.info("运行测试批改任务")
    logger.info("=" * 60)
    
    try:
        from functions.langgraph.workflow_new import run_production_grading
        from datetime import datetime
        
        # 测试数据
        test_state = {
            'task_id': f'test_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'user_id': 'test_user',
            'question_files': ['test_data/三角形题目.txt'],
            'answer_files': ['test_data/学生答案_三角形.txt'],
            'marking_files': ['test_data/三角形评分标准.txt'],
            'mode': 'efficient'  # 使用高效模式测试
        }
        
        logger.info(f"测试任务ID: {test_state['task_id']}")
        logger.info("开始执行批改...")
        
        result = await run_production_grading(**test_state)
        
        logger.info("=" * 60)
        logger.info("批改完成！")
        logger.info("=" * 60)
        logger.info(f"总分: {result.get('total_score', 0)}/{result.get('max_score', 0)}")
        logger.info(f"等级: {result.get('grade_level', 'N/A')}")
        logger.info(f"状态: {result.get('completion_status', 'unknown')}")
        
        if result.get('errors'):
            logger.warning(f"错误数: {len(result['errors'])}")
            for err in result['errors']:
                logger.error(f"  - {err}")
        
        return True
    except Exception as e:
        logger.error(f"✗ 测试批改失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_dependencies():
    """检查必要的依赖"""
    logger.info("检查依赖...")
    
    required_packages = [
        'langgraph',
        'sqlalchemy',
        'streamlit',
        'python-dotenv'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            logger.info(f"✓ {package}")
        except ImportError:
            logger.error(f"✗ {package} (未安装)")
            missing.append(package)
    
    if missing:
        logger.error(f"缺少依赖: {', '.join(missing)}")
        logger.info("请运行: pip install " + " ".join(missing))
        return False
    
    logger.info("✓ 所有依赖已安装")
    return True


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("AI批改系统 - 本地运行器")
    print("=" * 60 + "\n")
    
    # 1. 检查依赖
    if not check_dependencies():
        return
    
    # 2. 初始化数据库
    if not init_local_database():
        return
    
    # 3. 测试工作流
    if not test_workflow():
        return
    
    print("\n" + "=" * 60)
    print("✓ 本地环境检查通过！")
    print("=" * 60 + "\n")
    
    # 4. 询问是否运行测试
    choice = input("是否运行测试批改任务？(y/n): ").strip().lower()
    if choice == 'y':
        import asyncio
        asyncio.run(run_test_grading())
    else:
        print("\n启动Streamlit应用...")
        print("运行命令: streamlit run main.py")
        print("\n或者使用start_dev.bat启动")


if __name__ == '__main__':
    # 创建logs目录
    os.makedirs('logs', exist_ok=True)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序已中断")
    except Exception as e:
        logger.error(f"运行失败: {e}")
        import traceback
        traceback.print_exc()
