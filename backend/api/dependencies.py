"""
全局应用状态 — 管理共享组件与会话级 Agent 创建
"""

import logging
from fastapi import Request, Depends, HTTPException
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from api.config import ApiConfig
from config import AppConfig

from infrastructure.model_manager import ModelManager
from memory.short_term import ConversationMemory
from memory.conversation_store_db import DbConversationStore
from memory.long_term import AllenMemory
from agents.allen_agent import AllenAgent
from agents.reflect import ReflectEngine
from services.rag.engine import RAGApp
from services.search.router import SearchRouter
from guardrails.guardrail import Guardrail
from observability.tracer import Tracer

from tools.knowledge_tool import KnowledgeBaseTool
from tools.search_tool import SearchWebTool
from tools.file_tool import FileTool
from tools.image_tool import ImageTool
from tools.memory_tool import UpdateMemoryTool
from tools.shell_tool import ShellTool
from tools.search_code_tool import CodeSearchTool
from tools.pdf_tool import PDFTool

from db.database import get_db
from services.auth_service import decode_access_token, get_user_by_id

logger = logging.getLogger(__name__)

# HTTP Bearer token 安全方案
security = HTTPBearer(auto_error=False)

logger = logging.getLogger(__name__)


def get_app_state(request: Request) -> "AppState":
    """FastAPI 依赖注入"""
    return request.app.state.app_state


class AppState:
    """共享组件（模型、RAG、搜索、护栏）+ 会话级 Agent 工厂"""

    def __init__(self, api_config: ApiConfig):
        self.api_config = api_config
        self.config = AppConfig.from_env()
        self.store = DbConversationStore()

        logger.info("[API] 初始化模型管理器...")
        self.model_manager = ModelManager(self.config)
        llm = self.model_manager.current_provider

        logger.info("[API] 初始化 RAG 引擎...")
        self.rag_app = RAGApp(
            collection_name="agent_knowledge",
            llm_provider=llm,
            enable_search=False,
        )

        logger.info("[API] 初始化搜索路由...")
        self.search_router = SearchRouter(
            baidu_api_key=self.config.baidu_api_key,
            tavily_api_key=self.config.tavily_api_key,
            timeout=self.config.search_timeout,
        ) if (self.config.baidu_api_key or self.config.tavily_api_key) else None

        self.guardrail = Guardrail(require_confirm_for_write=False)
        self.reflect_engine = ReflectEngine(
            llm_provider=llm,
            max_reflections=self.config.max_reflections,
        )
        self.tracer = Tracer(verbose=False)

        # 基础工具（不含 UpdateMemoryTool，它在 create_agent 中按用户创建）
        self._base_tools = [
            KnowledgeBaseTool(rag_engine=self.rag_app.engine),
            SearchWebTool(search_router=self.search_router),
            FileTool(), ImageTool(),
            ShellTool(), PDFTool(), CodeSearchTool(),
        ]

        logger.info("[API] 初始化完成")

    def create_agent(self, session_id: str | None = None, user_id: str | None = None) -> AllenAgent:
        memory = ConversationMemory(max_turns=self.config.max_turns)
        if session_id:
            try:
                loaded = self.store.load(session_id)
                memory.set_messages(loaded.get_history())
            except FileNotFoundError:
                pass

        # 按用户创建独立持久记忆
        user_memory = AllenMemory(user_id=user_id)

        agent = AllenAgent(
            name="Allen_Agent",
            llm_provider=self.model_manager.current_provider,
            memory=memory,
            tracer=self.tracer,
            allen_memory=user_memory,
            guardrail=self.guardrail,
            reflect_engine=self.reflect_engine,
            max_steps=self.config.max_steps,
        )

        # 注册工具（含按用户隔离的 UpdateMemoryTool）
        for t in self._base_tools:
            agent.register_tool(t)
        memory_tool = UpdateMemoryTool()
        memory_tool.set_memory(user_memory)
        agent.register_tool(memory_tool)

        return agent

    def shutdown(self):
        logger.info("[API] 关闭中...")


# ═══════════════════════════════════════════════════════════════
# 用户认证依赖
# ═══════════════════════════════════════════════════════════════

async def get_current_user(
    credentials: HTTPBearer = Depends(security),
    db: Session = Depends(get_db),
) -> dict | None:
    """解析 JWT → 返回当前用户信息（可选认证）

    注意：如果 Authorization header 不存在，返回 None。
    路由需要强制认证时，在路由上声明这个依赖即可。
    """
    if credentials is None:
        return None

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(401, "无效的访问令牌")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "无效的访问令牌")

    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(401, "用户不存在")

    return user


async def get_required_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """强制要求登录的依赖（get_current_user 的严格版本）"""
    if current_user is None:
        raise HTTPException(401, "请先登录")
    return current_user
