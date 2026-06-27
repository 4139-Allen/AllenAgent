"""
文档处理层（加载 + 分块）
"""

from pathlib import Path


class DocumentProcessor:

    def load_text(self, text: str, source: str = "inline") -> list[dict]:
        """直接加载文本字符串"""
        return [{"content": text, "source": source, "page": 0}]

    def load_file(self, filepath: str) -> list[dict]:
        """加载单个文件（支持 .txt / .md）"""
        path = Path(filepath)
        content = path.read_text(encoding="utf-8")
        return [{"content": content, "source": path.name, "page": 0}]

    def load_folder(self, folder_path: str, extensions: list[str] = None) -> list[dict]:
        """
        批量加载文件夹中的所有文档

        Args:
            folder_path: 文件夹路径
            extensions: 支持的文件扩展名，默认 [".txt", ".md"]

        Returns:
            文档列表
        """
        if extensions is None:
            extensions = [".txt", ".md"]

        folder = Path(folder_path)
        if not folder.exists():
            print(f"[警告] 文件夹不存在: {folder_path}")
            return []

        docs = []
        for ext in extensions:
            for file_path in folder.rglob(f"*{ext}"):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    # 使用相对路径作为来源标识
                    source = str(file_path.relative_to(folder))
                    docs.append({
                        "content": content,
                        "source": source,
                        "page": 0,
                    })
                    print(f"  [加载] {source}")
                except Exception as e:
                    print(f"  [错误] 加载 {file_path} 失败: {e}")

        print(f"[文档加载] 共加载 {len(docs)} 个文件")
        return docs

    def split_chunks(
        self,
        docs: list[dict],
        chunk_size: int = 300,
        overlap: int = 50,
    ) -> list[dict]:
        """
        滑动窗口分块。
        chunk_size: 每块字符数
        overlap:    相邻块重叠字符数（保留上下文连续性）
        """
        chunks = []
        for doc in docs:
            text = doc["content"]
            start = 0
            idx = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "id": f"{doc['source']}__chunk{idx}",
                        "content": chunk_text,
                        "source": doc["source"],
                        "chunk_idx": idx,
                    })
                    idx += 1
                start += chunk_size - overlap
        print(f"[分块] 生成 {len(chunks)} 个 chunks（size={chunk_size}, overlap={overlap}）")
        return chunks
