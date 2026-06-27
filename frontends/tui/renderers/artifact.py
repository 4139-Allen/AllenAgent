"""制品渲染器 — artifact 事件

展示代码块、文件内容等结构化输出，带语法高亮和文件信息。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from frontends.tui.renderers.base import BaseRenderer
from frontends.tui.renderers.registry import register
from frontends.tui.widgets.artifact import ArtifactWidget

if TYPE_CHECKING:
    from frontends.tui.widgets.chat_panel import ChatPanel
    from schemas.stream import StreamEvent


@register("artifact")
class ArtifactRenderer(BaseRenderer):
    """渲染代码/文件内容制品"""

    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        # 语言推断：优先用 name，其次从 file_path 猜
        language = event.name
        if not language and event.file_path:
            language = ArtifactWidget.detect_language(event.file_path)

        widget = ArtifactWidget(
            content=event.content,
            language=language,
            title=event.file_path or "",
        )
        panel.add_artifact(widget)
