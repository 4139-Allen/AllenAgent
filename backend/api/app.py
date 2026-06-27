"""
FastAPI 应用工厂
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import ApiConfig
from api.dependencies import AppState
from api.routers import chat, conversations, models, memory, health

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
    return app


app = create_app()
