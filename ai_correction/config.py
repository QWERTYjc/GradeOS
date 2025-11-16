#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件
"""

import os
from pathlib import Path

# 加载.env文件
try:
    from dotenv import load_dotenv
    # 优先加载项目根目录的.env文件
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # 如果不存在，尝试加载父目录的.env文件
        parent_env = Path(__file__).parent.parent / '.env'
        if parent_env.exists():
            load_dotenv(parent_env)
        else:
            # 最后尝试加载当前目录的.env
            load_dotenv()
except ImportError:
    # 如果没有安装python-dotenv，跳过
    pass

# 项目根目录
BASE_DIR = Path(__file__).parent

# 数据库配置
DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'json')  # postgresql, mysql, json
DATABASE_URL = os.getenv('DATABASE_URL', '')

# PostgreSQL 默认配置（Railway）
if not DATABASE_URL and DATABASE_TYPE == 'postgresql':
    DATABASE_URL = os.getenv(
        'PGDATABASE',
        'postgresql://postgres:password@localhost:5432/ai_correction'
    )

# MySQL 默认配置（Railway）
if not DATABASE_URL and DATABASE_TYPE == 'mysql':
    DATABASE_URL = os.getenv(
        'MYSQL_URL',
        'mysql://root:password@localhost:3306/ai_correction'
    )

# LLM 配置
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openrouter')  # gemini, openai, openrouter
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'google/gemini-2.5-flash-lite')

# Gemini 配置
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', LLM_API_KEY)
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp')

# OpenAI 配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', LLM_API_KEY)
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4')

# OpenRouter 配置
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', LLM_API_KEY)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'google/gemini-2.5-flash-lite')

# 文件上传配置
UPLOAD_DIR = BASE_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = ['.txt', '.md', '.json', '.csv']

# 批改配置
DEFAULT_MAX_SCORE = 10  # 每题默认满分
PASS_THRESHOLD = 0.6  # 及格线（60%）

# 缓存配置
ENABLE_CACHE = os.getenv('ENABLE_CACHE', 'true').lower() == 'true'
CACHE_TTL = int(os.getenv('CACHE_TTL', '3600'))  # 1小时

# 日志配置
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = BASE_DIR / 'logs' / 'app.log'
LOG_FILE.parent.mkdir(exist_ok=True)

# Streamlit 配置
STREAMLIT_PORT = int(os.getenv('PORT', '8501'))
STREAMLIT_HOST = os.getenv('HOST', '0.0.0.0')

# Firebase 配置（如果使用）
FIREBASE_CONFIG = {
    'apiKey': os.getenv('FIREBASE_API_KEY', ''),
    'authDomain': os.getenv('FIREBASE_AUTH_DOMAIN', ''),
    'projectId': os.getenv('FIREBASE_PROJECT_ID', ''),
    'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET', ''),
    'messagingSenderId': os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
    'appId': os.getenv('FIREBASE_APP_ID', '')
}

# ============ 图片优化配置 ============

# Textin API 配置
TEXTIN_APP_ID = os.getenv('TEXTIN_APP_ID', '')
TEXTIN_SECRET_CODE = os.getenv('TEXTIN_SECRET_CODE', '')
TEXTIN_API_URL = os.getenv(
    'TEXTIN_API_URL',
    'https://api.textin.com/ai/service/v1/crop_enhance_image'
)

# 图片优化功能开关
ENABLE_IMAGE_OPTIMIZATION = os.getenv('ENABLE_IMAGE_OPT', 'false').lower() == 'true'
OPTIMIZATION_MODE = os.getenv('OPT_MODE', 'smart')  # smart, fast, deep, crop_only
AUTO_OPTIMIZE = os.getenv('OPT_AUTO_OPTIMIZE', 'false').lower() == 'true'
KEEP_ORIGINAL = os.getenv('OPT_KEEP_ORIGINAL', 'true').lower() == 'true'

# 图片优化参数
IMAGE_OPTIMIZATION_CONFIG = {
    'enabled': ENABLE_IMAGE_OPTIMIZATION,
    'mode': OPTIMIZATION_MODE,
    'api': {
        'timeout': 30,
        'retry': 2,
        'max_concurrent': 3
    },
    'quality': {
        'min_score': 60,
        'blur_threshold': 100,
        'size_min': 500
    },
    'storage': {
        'output_dir': str(BASE_DIR / 'temp' / 'uploads' / 'optimized'),
        'original_dir': str(BASE_DIR / 'temp' / 'uploads' / 'original'),
        'backup_dir': str(BASE_DIR / 'user_uploads' / 'backup')
    },
    'presets': {
        'smart': {
            'enhance_mode': 2,  # 增强并锐化
            'crop_image': 1,
            'dewarp_image': 1,
            'deblur_image': 1,
            'correct_direction': 1,
            'jpeg_quality': 85
        },
        'fast': {
            'enhance_mode': 1,  # 增亮
            'crop_image': 1,
            'dewarp_image': 1,
            'deblur_image': 0,
            'correct_direction': 0,
            'jpeg_quality': 85
        },
        'deep': {
            'enhance_mode': 5,  # 去阴影增强
            'crop_image': 1,
            'dewarp_image': 1,
            'deblur_image': 1,
            'correct_direction': 1,
            'jpeg_quality': 90
        },
        'crop_only': {
            'enhance_mode': -1,  # 禁用增强
            'crop_image': 1,
            'dewarp_image': 0,
            'deblur_image': 0,
            'correct_direction': 0,
            'jpeg_quality': 85
        }
    }
}

# 创建图片优化目录
for dir_key in ['output_dir', 'original_dir', 'backup_dir']:
    dir_path = Path(IMAGE_OPTIMIZATION_CONFIG['storage'][dir_key])
    dir_path.mkdir(parents=True, exist_ok=True)

