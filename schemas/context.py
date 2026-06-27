"""感知上下文数据模型"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PerceptionContext:
    """
    统一的感知上下文
    所有输入类型经过感知层处理后的标准化结构
    """
    text: str                                    # 最终文本（注入 prompt）
    source_type: str                             # "text" / "file" / "image" / "stream"
    original_size: int = 0                       # 原始大小（字符数）
    truncated: bool = False                      # 是否被截断
    metadata: dict = field(default_factory=dict) # 附加信息（文件名、语言等）

    @property
    def size(self) -> int:
        """处理后文本大小"""
        return len(self.text)

    @property
    def compression_ratio(self) -> float:
        """压缩比（处理后/原始）"""
        if self.original_size == 0:
            return 1.0
        return self.size / self.original_size
