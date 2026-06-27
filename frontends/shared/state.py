"""共享状态容器 — TUI 和 CLI 共用"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AppState:
    """应用共享状态（类型安全）"""
    agent: object          # AllenAgent
    memory: object         # ConversationMemory
    allen_memory: object   # AllenMemory
    model_manager: object  # ModelManager
    current_id: Optional[str] = None
