"""
Agent 基类
所有 Agent 都继承自 BaseAgent
"""

from abc import ABC, abstractmethod
from typing import Any
from tools.base import BaseTool
from schemas.tool import ToolResult


class BaseAgent(ABC):
    """
    Agent 基类
    实现工具注册、调度、执行的核心逻辑
    """

    def __init__(self, name: str = "BaseAgent"):
        self.name = name
        self.tools: dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.name] = tool
        print(f"[{self.name}] 注册工具: {tool.name}")

    def get_tools_schema(self) -> list[dict]:
        """
        获取所有工具的 Schema（OpenAI Function Calling 格式）

        返回格式：
        [
            {
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "...",
                    "parameters": { ... }
                }
            },
            ...
        ]
        """
        return [
            {"type": "function", "function": tool.get_schema()}
            for tool in self.tools.values()
        ]

    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        执行指定工具

        Args:
            tool_name: 工具名称
            **kwargs: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                data=None,
                error=f"工具 '{tool_name}' 不存在",
                source="agent"
            )

        tool = self.tools[tool_name]
        return tool.execute(**kwargs)

    @abstractmethod
    def run(self, query: str, verbose: bool = True) -> dict:
        """
        运行 Agent

        Args:
            query: 用户查询
            verbose: 是否打印详细信息

        Returns:
            dict: 包含答案和元信息
        """
        pass

    def __repr__(self):
        return f"<{self.name} tools={list(self.tools.keys())}>"
