"""
全局应用状态 — 管理共享组件与会话级 Agent 创建
"""

import logging
from fastapi import Request

from api.config import ApiConfig
from config import AppConfig

from infrastructure.model_manager import ModelManager
from memory.short_term import ConversationMemory
from memory.conversation_store import ConversationStore
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

logger = logging.getLogger(__name__)


def get_app_state(request: Request) -> "AppState":
    """FastAPI 依赖注入"""
    return request.app.state.app_state


class AppState:
    """共享组件（模型、RAG、搜索、护栏）+ 会话级 Agent 工厂"""

    def __init__(self, api_config: ApiConfig):
        self.api_config = api_config
        self.config = AppConfig.from_env()
        self.store = ConversationStore()
        self.allen_memory = AllenMemory()

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

        self._tools = [
            KnowledgeBaseTool(rag_engine=self.rag_app.engine),
            SearchWebTool(search_router=self.search_router),
            FileTool(), ImageTool(),
            UpdateMemoryTool().set_memory(self.allen_memory),
            ShellTool(), PDFTool(), CodeSearchTool(),
        ]

        logger.info("[API] 初始化完成")

    def create_agent(self, session_id: str | None = None) -> AllenAgent:
        memory = ConversationMemory(max_turns=self.config.max_turns)
        if session_id:
            try:
                loaded = self.store.load(session_id)
                memory.set_messages(loaded.get_history())
            except FileNotFoundError:
                pass

        agent = AllenAgent(
            name="Allen_Agent",
            llm_provider=self.model_manager.current_provider,
            memory=memory,
            tracer=self.tracer,
            allen_memory=self.allen_memory,
            guardrail=self.guardrail,
            reflect_engine=self.reflect_engine,
            max_steps=self.config.max_steps,
        )
        for t in self._tools:
            agent.register_tool(t)
        return agent

    def shutdown(self):
        logger.info("[API] 关闭中...")
