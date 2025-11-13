#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件
"""

import os
from pathlib import Path

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

