"""文件变更渲染器 — file_change

在推理块中高亮显示文件变更，例如：
  update config.py
  ┌─────────────────────┐
  │ DEBUG = True        │
  └─────────────────────┘
  delete old_file.txt
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from frontends.tui.renderers.base import BaseRenderer
from frontends.tui.renderers.registry import register

if TYPE_CHECKING:
    from frontends.tui.widgets.chat_panel import ChatPanel
    from schemas.stream import StreamEvent

_ACTION_COLORS = {
    "update":  "bold #4a9eff",   # 蓝色
    "created":  "bold #5abf7a",   # 绿色
    "deleted":  "bold #e06060",   # 红色
    "read":     "dim",            # 灰色（只读，不醒目）
}
_ACTION_LABELS = {
    "update":  "update",
    "created":  "created",
    "deleted":  "delete",
    "read":     "read",
}


@register("file_change")
class FileChangeRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        action = event.file_action or "update"
        path = event.file_path or ""
        filename = Path(path).name if path else ""
        color = _ACTION_COLORS.get(action, "bold #4a9eff")
        label = _ACTION_LABELS.get(action, action)
        block = panel.get_or_create_thought_block()
        # update/created 由永久 artifact 展示，thought block 不再重复
        if action not in ("update", "created"):
            block.append_colored(f"  {label} {filename}", color)

        # 完整内容由永久 artifact 展示，此处仅显示操作行
