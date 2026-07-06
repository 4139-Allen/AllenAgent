"""
数据库连接管理

连接策略（按优先级）：
  1. DATABASE_URL 环境变量（Docker 部署时设为 MySQL）
  2. 默认 SQLite（本地开发）
"""

import os
import logging
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

# ── 数据库 URL ────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")


def _ensure_database_exists():
    """MySQL 连接前自动建库，避免手动 CREATE DATABASE"""
    if not DATABASE_URL.startswith("mysql"):
        return

    parsed = urlparse(DATABASE_URL)
    db_name = parsed.path.lstrip("/").split("?")[0]
    if not db_name:
        return

    # 连接到 MySQL（不指定数据库），执行 CREATE DATABASE IF NOT EXISTS
    base_url = (
        f"mysql+pymysql://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 3306}"
    )

    try:
        temp_engine = create_engine(base_url)
        with temp_engine.connect() as conn:
            conn.execute(
                text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")
            )
            conn.commit()
        temp_engine.dispose()
        logger.info("[DB] 数据库 '%s' 已就绪（自动建库）", db_name)
    except Exception as e:
        logger.warning(
            "[DB] 自动建库失败: %s\n"
            "  可手动执行: CREATE DATABASE `%s` CHARACTER SET utf8mb4;",
            e, db_name,
        )


if not DATABASE_URL:
    # 默认 SQLite（本地开发）
    DATA_DIR = Path(__file__).parent.parent / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{DATA_DIR / 'allen_agent.db'}"
    _connect_args = {"check_same_thread": False}
    logger.info("[DB] 使用 SQLite: %s", DATA_DIR / "allen_agent.db")
else:
    _connect_args = {}
    logger.info("[DB] 使用外部数据库")
    # 自动建库（MySQL 专用）
    _ensure_database_exists()


engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：获取数据库 session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """建表"""
    from db import models  # noqa
    Base.metadata.create_all(bind=engine)
    logger.info("[DB] 数据库表已就绪")
