"""思考组件 — 紧凑显示"""
import time
from textual.widgets import Static
from rich.text import Text
from rich.console import Group


class ThinkingWidget(Static):
    """思考过程显示"""

    can_focus = True
    DEFAULT_CSS = """
    ThinkingWidget {
        height: auto;
        min-height: 1;
        margin: 0;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._content = ""
        self._expanded = False
        self._done = False
        self._start_time = time.time()
        self._token_count = 0

    def render(self):
        if self._done:
            elapsed = self._final_elapsed
        else:
            elapsed = max(1, int(time.time() - self._start_time))
        tokens = self._token_count

        line = Text()
        if self._done:
            line.append(f" thinking ({elapsed}s)", style="dim")
            if tokens:
                line.append(f" | {tokens} chars", style="dim")
        else:
            line.append(f" thinking... ({elapsed}s)", style="dim")

        if not self._expanded:
            line.append(" | ctrl+o", style="dim")

        parts = [line]

        if self._expanded and self._content:
            content_lines = self._content.split("\n")
            content_text = "\n".join(content_lines[:15])
            if len(content_lines) > 15:
                content_text += f"\n... {len(content_lines)} lines"
            parts.append(Text(f"  {content_text}", style="dim"))

        return Group(*parts)

    def toggle(self):
        self._expanded = not self._expanded
        self.refresh(layout=True)

    def append_content(self, token: str):
        if token:
            self._content += token
            self._token_count += len(token)
        self.refresh(layout=True)

    def finish(self):
        self._final_elapsed = max(1, int(time.time() - self._start_time))
        self._done = True
        self.refresh(layout=True)
