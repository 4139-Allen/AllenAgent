"""确认对话框渲染器 — confirm

负责安装/拆卸确认对话框 UI，异步等待由 stream_handler 处理。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import OptionList

from frontends.tui.renderers.base import BaseRenderer
from frontends.tui.renderers.registry import register
from frontends.tui.widgets.confirm_widget import ConfirmWidget

if TYPE_CHECKING:
    from frontends.tui.widgets.chat_panel import ChatPanel
    from frontends.tui.widgets.input_bar import InputBar
    from schemas.stream import StreamEvent


@register("confirm")
class ConfirmRenderer(BaseRenderer):
    """确认对话框安装/拆卸"""

    def render(self, panel: ChatPanel, event: StreamEvent) -> None:
        """安装确认对话框（返回前挂起 thought，禁用输入）"""
        # 挂起推理计时
        if panel._current_thought:
            panel._current_thought.pause()

        # 禁用输入栏
        try:
            input_bar = panel.app.query_one(InputBar)
            input_bar.disabled = True
        except Exception:
            pass

        # 从事件中提取文件路径
        file_path = ""
        if event.name == "file_io":
            file_path = event.args.get("filepath", "")

        # 创建并挂载确认组件（含 diff 预览）
        widget = ConfirmWidget(
            question=event.confirm_question,
            diff_content=event.content,  # 预计算的 diff
            file_path=file_path,
        )
        panel.mount(widget)
        # 等待 DOM 就绪后再聚焦，否则焦点设置不生效
        widget.call_after_refresh(
            lambda: widget.query_one(OptionList).focus()
        )

    @staticmethod
    def cleanup(panel: ChatPanel) -> None:
        """拆卸确认对话框（恢复推理计时，启用输入）"""
        try:
            input_bar = panel.app.query_one(InputBar)
            input_bar.disabled = False
            input_bar.focus_input()
        except Exception:
            pass

        if panel._current_thought:
            panel._current_thought.resume()

        # 移除已有的 ConfirmWidget
        for child in list(panel.children):
            if isinstance(child, ConfirmWidget):
                child.remove()
