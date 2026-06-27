"""消息组件"""
from textual.widgets import Static
from rich.text import Text
from rich.console import Group
from rich.markdown import Markdown


class UserMessage(Static):
    """用户消息 — 灰底"""
    can_focus = False
    DEFAULT_CSS = """
    UserMessage {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
        background: $surface-lighten-1;
    }
    """

    def __init__(self, content="", **kwargs):
        super().__init__(**kwargs)
        self.msg_content = str(content) if content else ""

    def render(self):
        lines = self.msg_content.split("\n")
        result = []
        for line in lines:
            result.append(Text(f"❯ {line}"))
        return Group(*result) if result else Text("❯ ")


class AssistantMessage(Static):
    """Agent 回复 — Rich Markdown 渲染"""
    can_focus = False
    DEFAULT_CSS = """
    AssistantMessage {
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.msg_content = ""
        self.is_streaming = True
        self._elapsed: int | None = None

    def render(self):
        cursor = "▌" if self.is_streaming else ""
        display_text = self.msg_content.strip()

        if not display_text:
            return Text.from_markup("[dim]● 正在思考...[/]")

        # ● 前缀融入 Markdown（而非独立 Text），避免 Group 布局错行
        parts = [Markdown(f"● {display_text}{cursor}", code_theme="monokai")]

        if self._elapsed is not None:
            parts.append(Text(f"\n━ 耗时 {self._elapsed}s", style="dim"))

        return Group(*parts)

    def append_token(self, token: str):
        if token:
            self.msg_content += token
        self.refresh(layout=True)

    def set_content(self, content):
        self.msg_content = str(content) if content else ""
        self.is_streaming = False
        self.refresh()

    def finalize(self, elapsed: int | None = None):
        self.is_streaming = False
        if elapsed is not None:
            self._elapsed = elapsed
        self.refresh()
