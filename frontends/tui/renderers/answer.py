"""最终答案渲染器 — token / done"""

from __future__ import annotations

from typing import TYPE_CHECKING

from frontends.tui.renderers.base import BaseRenderer
from frontends.tui.renderers.registry import register

if TYPE_CHECKING:
    from frontends.tui.widgets.chat_panel import ChatPanel
    from schemas.stream import StreamEvent


@register("token")
class TokenRenderer(BaseRenderer):
    """最终答案逐 token 渲染"""
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        panel.append_token(event.content)


@register("done")
class DoneRenderer(BaseRenderer):
    """流结束"""
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        pass  # done 由 stream_handler 处理收尾逻辑
