"""Claude Code 风格工具调用组件 — 单行显示，无边框"""
from textual.widgets import Static
from rich.text import Text
from rich.console import Group

from utils.content_cleaner import strip_tool_result_content


def format_tool_args(name: str, args: dict) -> str:
    """格式化工具参数为简短摘要"""
    if not args:
        return ""

    if name == "web_search":
        queries = args.get("queries", args.get("query", ""))
        if isinstance(queries, list):
            queries = ", ".join(str(q) for q in queries)
        return f'"{queries}"' if queries else ""

    for key in ("query", "command", "file_path", "topic", "prompt", "filename", "url"):
        if key in args:
            val = str(args[key])
            if len(val) > 40:
                val = val[:37] + "..."
            return f'"{val}"'

    parts = []
    for k, v in args.items():
        val = str(v)
        if len(val) > 30:
            val = val[:27] + "..."
        parts.append(f"{k}={val}")
        if len(parts) >= 2:
            break
    return ", ".join(parts)


TOOL_STATUS_ICONS = {
    "success": ("✓", "green"),
    "error": ("✗", "magenta"),
    "rejected": ("⊘", "yellow"),
    "skipped": ("⊘", "dim"),
    "timeout": ("✗", "magenta"),
}

TOOL_ICONS = {
    "search_knowledge_base": "KB",
    "search_web": "WEB",
    "file_io": "FILE",
    "read_image": "IMG",
    "update_memory": "MEM",
    "shell": "SH",
}


class ToolCallWidget(Static):
    """Claude Code 风格工具调用 — 单行 + 可展开详情"""

    can_focus = True
    DEFAULT_CSS = """
    ToolCallWidget {
        height: auto;
        min-height: 1;
        margin: 0;
        padding: 0 1;
        color: $text-muted;
    }
    ToolCallWidget:focus {
        background: $surface;
    }
    ToolCallWidget.expanded {
        background: $surface;
    }
    """

    def __init__(self, tool_name: str, tool_args: dict = None, **kwargs):
        super().__init__(**kwargs)
        self.tool_name = tool_name
        self.tool_args = tool_args or {}
        self._status = "running"
        self._detail = ""
        self._duration = 0
        self._expanded = False
        self._summary_text = format_tool_args(tool_name, self.tool_args)

    def render(self):
        tool_icon = TOOL_ICONS.get(self.tool_name, "🔧")

        if self._status == "running":
            status_icon, status_color = "⟳", "yellow"
            status_text = "..."
        else:
            si, sc = TOOL_STATUS_ICONS.get(self._status, ("?", "dim"))
            status_icon, status_color = si, sc
            if self._duration:
                # duration 始终是毫秒
                secs = self._duration / 1000
                status_text = f"{secs:.1f}s" if secs >= 1 else f"{self._duration}ms"
            else:
                status_text = ""

        line = Text()
        line.append(f" {tool_icon} ", style="bold dim")
        line.append(self.tool_name, style="bold cyan")
        if self._summary_text:
            line.append(f" {self._summary_text}", style="dim")
        line.append(" │ ", style="dim")
        line.append(status_icon, style=f"bold {status_color}")
        if status_text:
            line.append(f" {status_text}", style=status_color)
        if not self._expanded:
            if self._status not in ("rejected",):
                line.append(" │ ctrl+o", style="dim")

        if self._expanded and self._detail:
            detail_lines = self._detail.split("\n")
            detail_text = "\n".join(detail_lines[:20])
            if len(detail_lines) > 20:
                detail_text += f"\n... 共 {len(detail_lines)} 行"
            parts.append(Text.from_markup(f"[dim]{detail_text}[/]"))

        return Group(*parts)

    def toggle(self):
        self._expanded = not self._expanded
        self.toggle_class("expanded")
        self.refresh(layout=True)

    def update_status(self, status: str, detail: str = "", duration: int = 0):
        if status:
            self._status = status
        if detail:
            cleaned = strip_tool_result_content(detail)
            if cleaned:
                self._detail = cleaned
        if duration:
            self._duration = duration
        self.refresh(layout=True)

    def update_result(self, result, duration: int = 0, status: str = ""):
        result_str = str(result) if result else ""
        if duration:
            self._duration = duration
        if result_str:
            cleaned = strip_tool_result_content(result_str)
            if cleaned:
                self._detail = cleaned
        if status:
            self._status = status
        elif self._status == "running":
            self._status = "success"
        self.refresh(layout=True)
