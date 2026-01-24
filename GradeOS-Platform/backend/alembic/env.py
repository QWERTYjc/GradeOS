"""Alembic 环境配置"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Alembic Config 对象
config = context.config

# Keep psycopg3 for SQLAlchemy when DATABASE_URL lacks a driver prefix.
def _normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return f"postgresql+psycopg://{url[len('postgresql://'):]}"
    if url.startswith("postgres://"):
        return f"postgresql+psycopg://{url[len('postgres://'):]}"
    return url

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从环境变量读取数据库 URL（如果存在）
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", _normalize_db_url(database_url))

# 目标元数据（暂时为 None，因为我们使用原生 SQL）
target_metadata = None


def run_migrations_offline() -> None:
    """在离线模式下运行迁移"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在在线模式下运行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
