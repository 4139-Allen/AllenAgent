"""系统反馈渲染器 — error / cancelled / confirm / planning_start"""

from __future__ import annotations

from typing import TYPE_CHECKING

from frontends.tui.renderers.base import BaseRenderer
from frontends.tui.renderers.registry import register

if TYPE_CHECKING:
    from frontends.tui.widgets.chat_panel import ChatPanel
    from schemas.stream import StreamEvent


@register("planning_start")
class PlanningStartRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        panel.get_or_create_thought_block().append_colored(f"\n{event.content}", "cyan")


@register("error")
class ErrorRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        panel.add_system_message(f"错误: {event.content}")


@register("cancelled")
class CancelledRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        pass  # cancelled 由 stream_handler break 处理
