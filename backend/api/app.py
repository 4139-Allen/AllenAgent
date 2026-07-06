"""
FastAPI 应用工厂
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import ApiConfig
from api.dependencies import AppState
from api.routers import chat, conversations, models, memory, health, profile, upload, auth

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = ApiConfig.from_env()
    app.state.config = cfg
    logger.info("=" * 50)
    logger.info("  Allen Agents API 启动")
    logger.info("  Swagger: http://%s:%s/docs", cfg.host, cfg.port)
    logger.info("=" * 50)
    app.state.app_state = AppState(cfg)
    yield
    app.state.app_state.shutdown()


def create_app() -> FastAPI:
    cfg = ApiConfig.from_env()
    app = FastAPI(
        title="Allen Agents API",
        description="RAG + ReAct Agent + 多引擎搜索 智能问答系统",
        version="1.1.0",
        docs_url="/docs" if cfg.docs_enabled else None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat.router, prefix="/api")
    app.include_router(conversations.router, prefix="/api")
    app.include_router(models.router, prefix="/api")
    app.include_router(memory.router, prefix="/api")
    app.include_router(health.router)
    app.include_router(profile.router)
    app.include_router(upload.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")

    # 启动时创建/更新数据库表
    from db.database import init_db, engine
    init_db()
    # 数据库迁移：新加列 / 删旧列
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            # 加 avatar_data / avatar_mime（已有表不会自动加）
            for col, col_type in (("avatar_data", "BLOB"), ("avatar_mime", "VARCHAR(20)")):
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
                except Exception:
                    pass  # 列已存在

            # 删 avatar_url（已废弃，改用 avatar_data）
            try:
                conn.execute(text("ALTER TABLE users DROP COLUMN avatar_url"))
                logger.info("[DB] users 表已清理: 删除 avatar_url 列")
            except Exception:
                pass  # 列已不存在或 SQLite 不支持

            conn.commit()
    except Exception:
        pass  # 兼容无 users 表的情况

    return app


app = create_app()
