"""
网络搜索工具
封装搜索路由器，提供网络搜索能力
"""

from datetime import datetime
from tools.base import BaseTool
from schemas.tool import ToolResult


class SearchWebTool(BaseTool):
    """
    网络搜索工具
    用于搜索互联网获取实时信息
    """

    def __init__(self, search_router=None):
        super().__init__(
            name="search_web",
            description="搜索互联网，获取实时信息。适用于查询天气、新闻、最新事件、实时数据等知识库中可能没有的信息。"
        )
        self.search_router = search_router

    def set_router(self, search_router):
        """设置搜索路由器（延迟绑定）"""
        self.search_router = search_router

    def execute(self, query: str, num_results: int = 5, **kwargs) -> ToolResult:
        """
        执行网络搜索

        Args:
            query: 搜索查询
            num_results: 返回结果数量

        Returns:
            ToolResult: 包含搜索结果
        """
        if not self.search_router:
            return ToolResult(
                success=False,
                data=None,
                error="搜索路由器未初始化",
                source="web_search"
            )

        if not query or not query.strip():
            return ToolResult(
                success=False,
                data=None,
                error="搜索内容不能为空",
                source="web_search"
            )

        try:
            # 如果查询包含时间相关关键词，自动添加日期
            time_keywords = ["天气", "新闻", "最新", "今天", "昨天", "明天", "最近"]
            needs_date = any(kw in query for kw in time_keywords)

            search_query = query.strip()
            if needs_date and not any(d in query for d in ["2024", "2025", "2026"]):
                today = datetime.now().strftime("%Y年%m月%d日")
                search_query = f"{search_query} {today}"

            # 执行搜索
            results = self.search_router.search(
                search_query,
                num_results=num_results,
                verbose=True  # 打印详细日志
            )

            if results:
                # 格式化结果
                formatted = [
                    {
                        "title": r.title,
                        "snippet": r.snippet,
                        "url": r.url,
                        "source": r.source,
                    }
                    for r in results
                ]
                return ToolResult(
                    success=True,
                    data=formatted,
                    source="web_search"
                )
            else:
                return ToolResult(
                    success=True,
                    data=[],
                    source="web_search"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                source="web_search"
            )

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询内容"
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认5",
                    "default": 5
                }
            },
            "required": ["query"]
        }
