"""
RAG 核心：检索 + 搜索 + 生成
依赖：infrastructure.embedding, infrastructure.vector_store, services.document
"""

from pathlib import Path

from infrastructure.embedding import EmbeddingModel
from infrastructure.vector_store import VectorStore
from services.rag.document import DocumentProcessor
from services.search.router import SearchRouter

# 项目根目录（向上三级：rag → services → 项目根）
PROJECT_ROOT = Path(__file__).parent.parent.parent


class RAGEngine:

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        vector_store: VectorStore,
        llm_provider=None,
        search_router: SearchRouter = None,
        top_k: int = 5,
        score_threshold: float = 0.5,
        enable_search: bool = True,
    ):
        self.embedder = embedding_model
        self.store = vector_store
        self.llm_provider = llm_provider
        self.search_router = search_router
        self.top_k = top_k
        self.score_threshold = score_threshold
        self.enable_search = enable_search

    def index(self, chunks: list[dict]):
        """把 chunks 向量化并存入数据库"""
        print(f"[索引] 正在 Embedding {len(chunks)} 个 chunks...")
        texts = [c["content"] for c in chunks]
        embeddings = self.embedder.embed(texts)
        self.store.add(chunks, embeddings)

    def retrieve(self, query: str) -> list[dict]:
        """
        检索知识库（公开接口，供 Tool 层调用）

        Args:
            query: 查询文本

        Returns:
            过滤后的相关结果列表
        """
        if not query or not query.strip():
            return []

        q_embedding = self.embedder.embed_one(query.strip())
        results = self.store.search(q_embedding, top_k=self.top_k)
        relevant = [r for r in results if r["score"] >= self.score_threshold]
        return relevant

    def query(self, question: str, verbose: bool = True) -> dict:
        """
        完整流程：
        1. 知识库检索
        2. 如果无结果且启用搜索 → 网络搜索
        3. 拼装 Prompt
        4. LLM 生成答案
        """
        # 空问题检查
        if not question or not question.strip():
            return {
                "question": question,
                "answer": "请输入有效的问题。",
                "retrieved": [],
                "search_results": [],
                "has_context": False,
                "source": "empty",
            }

        # Step 1: 知识库检索
        relevant = self.retrieve(question)

        if verbose:
            print(f"\n[检索] 问题：{question}")
            print(f"[检索] 知识库过滤后 {len(relevant)} 条相关")
            for i, r in enumerate(relevant):
                print(f"  [{i+1}] score={r['score']} | {r['content'][:60]}...")

        # Step 2: 如果知识库无结果，尝试网络搜索
        search_results = []
        if not relevant and self.enable_search and self.search_router:
            if verbose:
                print("[检索] 知识库无结果，启动网络搜索...")

            raw_results = self.search_router.search(question, verbose=verbose)
            search_results = [
                {
                    "content": f"{r.title}\n{r.snippet}",
                    "source": f"web:{r.source}",
                    "url": r.url,
                }
                for r in raw_results
            ]

            if verbose and search_results:
                print(f"[搜索] 获取到 {len(search_results)} 条网络结果")

        # Step 3: 拼装 Prompt
        if relevant:
            # 知识库有结果
            context = "\n\n".join(
                f"[来源: {r['source']}]\n{r['content']}"
                for r in relevant
            )
            prompt = f"""请根据以下参考资料回答问题。
如果参考资料中没有相关信息，请直接说明，不要编造内容。

参考资料：
{context}

问题：{question}

请给出简洁、准确的答案："""
        elif search_results:
            # 网络搜索有结果
            context = "\n\n".join(
                f"[来源: {r['source']}]\n{r['content']}"
                for r in search_results
            )
            prompt = f"""请根据以下网络搜索结果回答问题。
这些结果来自互联网，请注意甄别信息的准确性。

搜索结果：
{context}

问题：{question}

请给出简洁、准确的答案："""
        else:
            # 无任何结果，降级为纯 LLM
            prompt = f"{question}\n\n（注意：知识库和网络搜索均未找到相关文档，以下为模型自身知识）"
            if verbose:
                print("[检索] 无任何结果，降级为纯 LLM 模式")

        # Step 4: 生成
        result = self.llm_provider.chat(
            messages=[
                {"role": "system", "content": "你是一个准确、简洁的问答助手，回答基于提供的参考资料。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        if not result["success"]:
            return {
                "question": question,
                "answer": f"抱歉，生成答案时出错：{result['error']}",
                "retrieved": relevant,
                "search_results": search_results,
                "has_context": len(relevant) > 0 or len(search_results) > 0,
                "source": "error",
            }
        answer = result["content"]

        return {
            "question": question,
            "answer": answer,
            "retrieved": relevant,
            "search_results": search_results,
            "has_context": len(relevant) > 0 or len(search_results) > 0,
            "source": "knowledge_base" if relevant else ("web_search" if search_results else "llm_fallback"),
        }


class RAGApp:
    """封装好的 RAG 应用，对外只暴露 add_document / ask"""

    def __init__(
        self,
        collection_name: str = "default",
        llm_provider=None,
        enable_search: bool = True,
        baidu_api_key: str = None,
        tavily_api_key: str = None,
    ):
        self.embedder = EmbeddingModel(mode="local")
        self.store = VectorStore(collection_name=collection_name)
        self.processor = DocumentProcessor()

        # LLM Provider（如果不传则创建默认实例）
        if llm_provider is None:
            from infrastructure.llm_provider import create_default_provider
            llm_provider = create_default_provider()
        self.llm_provider = llm_provider

        # 搜索路由器（可选）
        self.search_router = None
        if enable_search:
            self.search_router = SearchRouter(
                baidu_api_key=baidu_api_key,
                tavily_api_key=tavily_api_key,
            )

        self.engine = RAGEngine(
            self.embedder,
            self.store,
            llm_provider=self.llm_provider,
            search_router=self.search_router,
            enable_search=enable_search,
        )

    def add_text(self, text: str, source: str = "manual"):
        """添加文本到知识库"""
        docs = self.processor.load_text(text, source)
        chunks = self.processor.split_chunks(docs, chunk_size=500, overlap=100)
        self.engine.index(chunks)

    def add_file(self, filepath: str):
        """添加单个文件到知识库"""
        docs = self.processor.load_file(filepath)
        chunks = self.processor.split_chunks(docs, chunk_size=500, overlap=100)
        self.engine.index(chunks)

    def add_docs_folder(self, folder_path: str = None):
        """
        批量加载 Rag_local_docs 文件夹中的所有文档

        Args:
            folder_path: 文件夹路径，默认为项目根目录下的 Rag_local_docs/
        """
        if folder_path is None:
            folder_path = str(PROJECT_ROOT / "Rag_local_docs")

        print(f"\n[加载文档] 扫描文件夹: {folder_path}")
        docs = self.processor.load_folder(folder_path)
        if docs:
            chunks = self.processor.split_chunks(docs, chunk_size=500, overlap=100)
            self.engine.index(chunks)
        else:
            print("[警告] 未找到任何文档")

    def ask(self, question: str) -> str:
        result = self.engine.query(question)
        return result["answer"]

    def ask_with_sources(self, question: str) -> dict:
        return self.engine.query(question)


# ════════════════════════════════════════════════
# 测试
# ════════════════════════════════════════════════
if __name__ == "__main__":
    app = RAGApp(
        collection_name="agent_knowledge",
        enable_search=True,  # 启用网络搜索
    )

    # ── 建库（如果向量库为空才加载） ──────────────────
    print("=== 建库阶段 ===\n")
    if app.store.count() == 0:
        print("[向量库为空，开始加载文档...]")
        app.add_docs_folder()
    else:
        print(f"[向量库已有 {app.store.count()} 条记录，跳过建库]")

    # ── 问答测试 ────────────────────────────────
    print("\n=== 问答阶段 ===\n")

    test_cases = [
        {
            "category": "📚 知识库命中",
            "questions": [
                "什么是 RAG？它有什么优势？",
                "DeepSeek 有哪些模型？有什么区别？",
                "智能体的核心循环是什么？",
            ]
        },
        {
            "category": "🌐 需要网络搜索",
            "questions": [
                "今天北京天气怎么样？",
                "2024年诺贝尔物理学奖得主是谁？",
            ]
        },
        {
            "category": "🤖 LLM 兜底",
            "questions": [
                "1+1等于几？",
                "为什么天空是蓝色的？",
            ]
        },
        {
            "category": "⚠️ 边界测试",
            "questions": [
                "",  # 空问题
                "a",  # 极短问题
                "你好",  # 简单问候
            ]
        },
    ]

    for group in test_cases:
        print(f"\n{'═'*60}")
        print(f"  {group['category']}")
        print(f"{'═'*60}")

        for q in group["questions"]:
            print(f"\n{'─'*50}")
            if not q:
                print("[跳过空问题]")
                continue

            result = app.ask_with_sources(q)
            print(f"问：{result['question']}")
            print(f"答：{result['answer'][:200]}{'...' if len(result['answer']) > 200 else ''}")
            print(f"来源类型：{result['source']}")
            if result["retrieved"]:
                print(f"知识库来源：{[r['source'] for r in result['retrieved']]}")
            if result.get("search_results"):
                print(f"网络搜索来源：{[r['source'] for r in result['search_results']]}")
