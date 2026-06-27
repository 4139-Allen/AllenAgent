"""可观测性相关数据模型"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceStep:
    """单步追踪记录"""
    step: int
    type: str           # "llm_call" / "tool_calls" / "tool_result" / "final_answer" / "error"
    content: Any
    tokens: int = 0
    latency: float = 0.0
    metadata: dict = field(default_factory=dict)
