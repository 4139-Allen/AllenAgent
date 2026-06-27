"""
Embedding 层
优先用 DeepSeek Embedding API（如已开放）
否则用本地 sentence-transformers（免费、离线）
"""


class EmbeddingModel:
    """
    两种选择：
    A) DeepSeek Embedding API（需检查是否开放）
    B) 本地 sentence-transformers（推荐学习用，完全免费）
    """

    def __init__(self, mode: str = "local", llm_provider=None):
        self.mode = mode
        self.llm_provider = llm_provider
        if mode == "local":
            from sentence_transformers import SentenceTransformer
            # 中英双语模型，512 维，效果不错
            # local_files_only=True: 仅使用本地缓存，避免网络检查
            try:
                self.model = SentenceTransformer(
                    "BAAI/bge-small-zh-v1.5",
                    local_files_only=True  # 强制使用本地缓存
                )
            except OSError:
                print("[Embedding] 本地模型未找到，请先下载：")
                print("  python -c \"from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')\"")
                print("  或设置 mode='remote' 使用 API 模式")
                raise
            print("[Embedding] 使用本地模型: BAAI/bge-small-zh-v1.5")
        else:
            if not self.llm_provider:
                raise ValueError("远程 embedding 模式需要传入 llm_provider")
            print("[Embedding] 使用 DeepSeek Embedding API")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.mode == "local":
            return self.model.encode(texts, normalize_embeddings=True).tolist()
        else:
            return self.llm_provider.embed(texts)

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]
