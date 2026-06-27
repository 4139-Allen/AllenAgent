"""
向量知识库（ChromaDB 封装）
"""

from pathlib import Path
import chromadb


class VectorStore:

    def __init__(self, collection_name: str = "my_knowledge", persist_dir: str = None):
        if persist_dir is None:
            # 使用项目目录下的 Vector_library/chroma_db
            project_root = Path(__file__).parent.parent
            persist_dir = str(project_root / "Vector_library" / "chroma_db")

        # 自动创建目录（如果不存在）
        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self.chroma = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.chroma.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # 余弦相似度
        )
        print(f"[VectorStore] collection='{collection_name}'，persist_dir='{persist_dir}'")
        print(f"[VectorStore] 已有 {self.collection.count()} 条记录")

    def add(self, chunks: list[dict], embeddings: list[list[float]]):
        """批量写入"""
        self.collection.upsert(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings,
            documents=[c["content"] for c in chunks],
            metadatas=[{"source": c["source"], "chunk_idx": c["chunk_idx"]} for c in chunks],
        )
        print(f"[VectorStore] 写入 {len(chunks)} 条，总计 {self.collection.count()} 条")

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        """检索最相似的 top_k 个 chunk"""
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "content": doc,
                "source": meta["source"],
                "score": round(1 - dist, 4),  # cosine distance → similarity
            })
        return chunks

    def count(self) -> int:
        return self.collection.count()
