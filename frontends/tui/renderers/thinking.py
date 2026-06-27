"""推理与工具调用渲染器 — thinking/tool_call/tool_result"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from frontends.tui.renderers.base import BaseRenderer
from frontends.tui.renderers.registry import register

if TYPE_CHECKING:
    from frontends.tui.widgets.chat_panel import ChatPanel
    from schemas.stream import StreamEvent


@register("thinking_start")
class ThinkingStartRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        pass  # ThoughtBlock 已由 panel.start_thought_block() 创建


@register("thinking_token")
class ThinkingTokenRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        panel.append_thought_thinking(event.content)


@register("thinking_end")
class ThinkingEndRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        pass  # done 时会统一关闭


@register("tool_call")
class ToolCallRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        if event.count > 1:
            summary = f"{event.name} ({event.count} 项)"
        else:
            args_str = json.dumps(event.args, ensure_ascii=False)
            summary = f"{event.name} {args_str}"
        panel.add_thought_tool_line(summary)


@register("tool_result")
class ToolResultRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        panel.finalize_tool_call()
        result_preview = str(event.result)[:200] if event.result else "无返回"
        panel.add_thought_tool_result_line(result_preview)


@register("reflection")
class ReflectionRenderer(BaseRenderer):
    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        """在推理块中显示反思摘要（紫色）"""
        label = f"反思 {event.ref_type}" if event.ref_type else "思考评估"
        text = f"↺ {label}: {event.summary}" if event.summary else f"↺ {label}"
        panel.get_or_create_thought_block().append_colored(text, "bold #ce93d8")
