"""
知识库工具
封装 RAG 引擎，提供知识库检索能力
"""

from tools.base import BaseTool
from schemas.tool import ToolResult


class KnowledgeBaseTool(BaseTool):
    """
    知识库检索工具
    用于搜索本地知识库中的文档
    """

    def __init__(self, rag_engine=None):
        super().__init__(
            name="search_knowledge_base",
            description="搜索本地知识库，获取内部文档信息。适用于查询已有知识、技术文档、内部资料等。"
        )
        self.rag_engine = rag_engine

    def set_engine(self, rag_engine):
        """设置 RAG 引擎（延迟绑定）"""
        self.rag_engine = rag_engine

    def execute(self, query: str, **kwargs) -> ToolResult:
        """
        执行知识库检索

        Args:
            query: 搜索查询

        Returns:
            ToolResult: 包含检索结果
        """
        if not self.rag_engine:
            return ToolResult(
                success=False,
                data=None,
                error="知识库引擎未初始化",
                source="knowledge_base"
            )

        if not query or not query.strip():
            return ToolResult(
                success=False,
                data=None,
                error="查询内容不能为空",
                source="knowledge_base"
            )

        try:
            # 只调用 engine 的公开方法，不穿透内部组件
            relevant = self.rag_engine.retrieve(query.strip())

            if relevant:
                return ToolResult(
                    success=True,
                    data=relevant,
                    source="knowledge_base"
                )
            else:
                return ToolResult(
                    success=True,
                    data=[],  # 空结果，不是错误
                    source="knowledge_base"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                source="knowledge_base"
            )

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题"
                }
            },
            "required": ["query"]
        }
