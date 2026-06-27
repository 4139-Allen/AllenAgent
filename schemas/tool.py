"""工具相关数据模型"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    data: Any
    error: str = None
    source: str = None  # 结果来源标识

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "source": self.source,
        }
