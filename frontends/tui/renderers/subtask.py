"""子任务进度渲染器 — subtask_start / subtask_done"""

from __future__ import annotations

from typing import TYPE_CHECKING

from frontends.tui.renderers.base import BaseRenderer
from frontends.tui.renderers.registry import register

if TYPE_CHECKING:
    from frontends.tui.widgets.chat_panel import ChatPanel
    from schemas.stream import StreamEvent


@register("subtask_start")
class SubtaskStartRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        panel.get_or_create_thought_block().start_subtask(event.content)


@register("subtask_done")
class SubtaskDoneRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        panel.get_or_create_thought_block().done_subtask()
