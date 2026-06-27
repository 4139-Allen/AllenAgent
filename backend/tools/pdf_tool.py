"""
PDF 读取工具
Agent 可通过此工具读取 PDF 文件内容
"""

from pathlib import Path
from tools.base import BaseTool
from schemas.tool import ToolResult


class PDFTool(BaseTool):
    """PDF 文件读取工具"""

    def __init__(self):
        super().__init__(
            name="read_pdf",
            description="读取 PDF 文件内容。支持指定页码范围。返回提取的文本内容。"
        )

    def execute(self, filepath: str, pages: str = None, **kwargs) -> ToolResult:
        """
        读取 PDF 文件

        Args:
            filepath: PDF 文件路径
            pages: 页码范围，如 "1-5"、"3"、"1,3,5"，不传则读取全部
        """
        path = Path(filepath).resolve()

        if not path.exists():
            return ToolResult(
                success=False,
                data=None,
                error=f"文件不存在: {filepath}",
                source="read_pdf",
            )

        if not path.suffix.lower() == ".pdf":
            return ToolResult(
                success=False,
                data=None,
                error=f"不是 PDF 文件: {filepath}",
                source="read_pdf",
            )

        try:
            import PyPDF2
        except ImportError:
            return ToolResult(
                success=False,
                data=None,
                error="PyPDF2 未安装，请运行: pip install PyPDF2",
                source="read_pdf",
            )

        try:
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                total_pages = len(reader.pages)

                # 解析页码范围
                page_indices = self._parse_pages(pages, total_pages)

                # 提取文本
                texts = []
                for i in page_indices:
                    if 0 <= i < total_pages:
                        page_text = reader.pages[i].extract_text()
                        if page_text and page_text.strip():
                            texts.append(f"--- 第 {i + 1} 页 ---\n{page_text.strip()}")

                if not texts:
                    return ToolResult(
                        success=True,
                        data={"filepath": str(path), "total_pages": total_pages, "content": "[PDF 无文本内容，可能是扫描件]"},
                        source="read_pdf",
                    )

                content = "\n\n".join(texts)

                # 截断过长内容
                if len(content) > 20000:
                    content = content[:20000] + f"\n\n[内容过长，已截断。共 {total_pages} 页]"

                return ToolResult(
                    success=True,
                    data={
                        "filepath": str(path),
                        "total_pages": total_pages,
                        "read_pages": len(page_indices),
                        "content": content,
                    },
                    source="read_pdf",
                )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=f"读取 PDF 失败: {e}",
                source="read_pdf",
            )

    def _parse_pages(self, pages: str | None, total_pages: int) -> list[int]:
        """解析页码范围字符串为页码索引列表（0-based）"""
        if not pages:
            return list(range(total_pages))

        indices = []
        for part in pages.split(","):
            part = part.strip()
            if "-" in part:
                # 范围：如 "1-5"
                try:
                    start, end = part.split("-", 1)
                    start = max(1, int(start.strip()))
                    end = min(total_pages, int(end.strip()))
                    indices.extend(range(start - 1, end))
                except ValueError:
                    continue
            else:
                # 单页：如 "3"
                try:
                    p = int(part)
                    if 1 <= p <= total_pages:
                        indices.append(p - 1)
                except ValueError:
                    continue

        return sorted(set(indices)) if indices else list(range(total_pages))

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "PDF 文件路径",
                },
                "pages": {
                    "type": "string",
                    "description": "页码范围，如 '1-5'、'3'、'1,3,5'，不传则读取全部",
                },
            },
            "required": ["filepath"],
        }
