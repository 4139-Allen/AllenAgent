"""Renderer 基类"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frontends.tui.widgets.chat_panel import ChatPanel
    from schemas.stream import StreamEvent


class BaseRenderer:
    """事件渲染器基类"""

    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        """渲染事件到面板"""
        raise NotImplementedError
