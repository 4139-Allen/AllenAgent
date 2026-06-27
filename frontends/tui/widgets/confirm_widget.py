"""极简确认对话框 — 上下键选择，回车确认，禁用点击"""
from textual import events
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option
from textual.message import Message
from rich.syntax import Syntax
from rich.panel import Panel
from rich.text import Text


class _KeyboardOnlyOptionList(OptionList):
    """只响应键盘回车，不响应鼠标点击"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keyboard_select = False

    def action_select(self):
        """Enter 键选择前标记为键盘触发"""
        self._keyboard_select = True
        super().action_select()
        self._keyboard_select = False

    def _on_option_selected(self, option_id):
        """鼠标触发的 _on_option_selected 被拦截（键盘 Enter 放行）"""
        if not self._keyboard_select:
            return
        super()._on_option_selected(option_id)

    def _on_key(self, event: events.Key) -> None:
        # ctrl+o 放行，交由 app 层展开/折叠思考内容
        if event.key == "ctrl+o":
            super()._on_key(event)
            return
        super()._on_key(event)


class DiffPreview(Static):
    """代码 diff 预览面板 — Rich Syntax + Panel 渲染"""

    DEFAULT_CSS = """
    DiffPreview {
        height: auto;
        margin: 1 2 0 2;
        padding: 0;
    }
    """

    def __init__(self, diff_content: str = "", file_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self._diff = str(diff_content) if diff_content else ""
        self._file_path = str(file_path) if file_path else ""

    def render(self):
        if not self._diff.strip():
            return Text("")

        # 删除操作等纯文本警告
        if self._diff.startswith("⚠"):
            return Text(self._diff, style="bold yellow")

        # diff 语法高亮
        syntax = Syntax(
            self._diff,
            "diff",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
            background_color="default",
        )
        title = f" {self._file_path}" if self._file_path else "变更预览"
        return Panel(
            syntax,
            title=title,
            border_style="#ff8c00",
            padding=(0, 1),
        )


class ConfirmWidget(Static):
    """确认对话框 — 上下键 + 回车，含代码 diff 预览"""

    DEFAULT_CSS = """
    ConfirmWidget {
        height: auto;
        min-height: 2;
        margin: 0;
        padding: 0 1;
        background: $surface;
    }
    #confirm-options {
        height: auto;
        max-height: 3;
        background: $surface;
        border: none;
        margin: 0;
        padding: 0;
    }
    #confirm-options:focus .option-list--option-highlighted {
        background: transparent;
        color: #64b5f6;
    }
    #confirm-options .option-list--option-highlighted {
        background: transparent;
        color: #64b5f6;
    }
    """

    class Confirmed(Message):
        def __init__(self, accepted: bool, auto_all: bool = False):
            super().__init__()
            self.accepted = accepted
            self.auto_all = auto_all

    def __init__(self, question: str = "", diff_content: str = "", file_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self.question = str(question) if question else ""
        self.diff_content = str(diff_content) if diff_content else ""
        self.file_path = str(file_path) if file_path else ""

    def compose(self):
        yield Static(f"  [bold yellow]⚠ {self.question}[/]")
        if self.diff_content:
            yield DiffPreview(self.diff_content, self.file_path)
        yield _KeyboardOnlyOptionList(
            Option("  ✓ 确认执行", id="yes"),
            Option("  ↻ 同类自动执行", id="auto"),
            Option("  ✗ 拒绝", id="no"),
            id="confirm-options",
        )

    def on_option_list_option_selected(self, event):
        if event.option_id == "yes":
            self.post_message(self.Confirmed(True, auto_all=False))
        elif event.option_id == "auto":
            self.post_message(self.Confirmed(True, auto_all=True))
        else:
            self.post_message(self.Confirmed(False, auto_all=False))
