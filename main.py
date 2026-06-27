"""
RAG Agent 主程序
整合 RAG 引擎、搜索引擎、工具、Agent
支持终端对话模式和 TUI 模式
"""

from pathlib import Path
from dotenv import load_dotenv

# 项目根目录
PROJECT_ROOT = Path(__file__).parent

# 加载环境变量
load_dotenv()

# ── 导入各模块 ──────────────────────────────────
from config import AppConfig
from services.rag.engine import RAGApp
from services.search.router import SearchRouter
from tools.knowledge_tool import KnowledgeBaseTool
from tools.search_tool import SearchWebTool
from tools.file_tool import FileTool
from tools.image_tool import ImageTool
from tools.memory_tool import UpdateMemoryTool
from tools.shell_tool import ShellTool
from tools.search_code_tool import CodeSearchTool
from agents.allen_agent import AllenAgent
from agents.reflect import ReflectEngine
from infrastructure.model_manager import ModelManager
from memory.short_term import ConversationMemory
from memory.conversation_store import ConversationStore
from memory.long_term import AllenMemory
from observability.tracer import Tracer
from guardrails.guardrail import Guardrail


def create_agent(
    collection_name: str = "agent_knowledge",
    enable_search: bool = True,
) -> tuple[AllenAgent, ModelManager]:
    """
    创建并配置 Allen Agent

    Returns:
        (AllenAgent, ModelManager)
    """
    config = AppConfig.from_env()

    print("=" * 60)
    print("  初始化 RAG Agent")
    print("=" * 60)

    # 0. 创建模型管理器
    print("\n[初始化] 模型管理器...")
    model_manager = ModelManager(config)
    llm_provider = model_manager.current_provider
    print(f"  -> 默认模型: {model_manager.current_model}")

    # 1. 创建 RAG 应用
    print("\n[初始化] RAG 引擎...")
    rag_app = RAGApp(
        collection_name=collection_name,
        llm_provider=llm_provider,
        enable_search=False,  # Agent 模式下，搜索由 Agent 控制
    )

    # 2. 建库（如果需要）
    if rag_app.store.count() == 0:
        print("[初始化] 知识库为空，加载文档...")
        rag_app.add_docs_folder()
    else:
        print(f"[初始化] 知识库已有 {rag_app.store.count()} 条记录")

    # 3. 创建搜索路由器（可选）
    search_router = None
    if enable_search:
        print("[初始化] 搜索路由器...")
        search_router = SearchRouter(
            baidu_api_key=config.baidu_api_key,
            tavily_api_key=config.tavily_api_key,
            timeout=config.search_timeout,
        )

    # 4. 创建工具
    print("[初始化] 注册工具...")
    knowledge_tool = KnowledgeBaseTool(rag_engine=rag_app.engine)
    search_tool = SearchWebTool(search_router=search_router)
    file_tool = FileTool()
    image_tool = ImageTool()
    memory_tool = UpdateMemoryTool()
    shell_tool = ShellTool()

    # PDF 工具
    from tools.pdf_tool import PDFTool
    pdf_tool = PDFTool()

    # 代码搜索工具
    code_search_tool = CodeSearchTool()

    # 5. 创建记忆和追踪器
    print("[初始化] 对话记忆和追踪器...")
    memory = ConversationMemory(max_turns=config.max_turns)
    tracer = Tracer(verbose=config.tracer_verbose)
    allen_memory = AllenMemory()
    memory_tool.set_memory(allen_memory)

    # 6. 创建安全护栏
    print("[初始化] 安全护栏...")
    guardrail = Guardrail(
        llm_provider=llm_provider,
        enable_llm_check=True,
    )

    # 7. 创建自我评估引擎
    print("[初始化] 自我评估引擎...")
    reflect_engine = ReflectEngine(
        llm_provider=llm_provider,
        max_reflections=config.max_reflections,
    )

    # 8. 创建 Agent
    print("[初始化] 创建 Agent...")
    agent = AllenAgent(
        name="Allen_Agent",
        llm_provider=llm_provider,
        memory=memory,
        tracer=tracer,
        allen_memory=allen_memory,
        guardrail=guardrail,
        reflect_engine=reflect_engine,
        max_steps=config.max_steps,
    )
    agent.register_tool(knowledge_tool)
    agent.register_tool(search_tool)
    agent.register_tool(file_tool)
    agent.register_tool(image_tool)
    agent.register_tool(memory_tool)
    agent.register_tool(shell_tool)
    agent.register_tool(pdf_tool)
    agent.register_tool(code_search_tool)

    print("\n" + "=" * 60)
    print("  RAG Agent 初始化完成")
    print("=" * 60)

    return agent, model_manager


def run_tui():
    """TUI 模式（Textual 界面）"""
    agent, model_manager = create_agent()
    config = AppConfig.from_env()
    store = ConversationStore()

    from frontends.tui.app import AllenApp
    app = AllenApp(agent=agent, config=config, store=store, model_manager=model_manager)
    try:
        app.run()
    except KeyboardInterrupt:
        pass


def run_cli():
    """终端对话模式"""
    agent, model_manager = create_agent()
    allen_memory = agent.allen_memory

    from frontends.cli.app import run_cli as _run_cli
    _run_cli(agent, model_manager, allen_memory)


if __name__ == "__main__":
    import sys

    if "--tui" in sys.argv:
        run_tui()
    else:
        run_cli()
