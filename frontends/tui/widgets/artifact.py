"""制品展示组件 — 代码块、文件内容、结构化输出的富文本渲染"""
from textual.widgets import Static
from rich.syntax import Syntax
from rich.text import Text
from rich.console import Group, RenderableType


class ArtifactWidget(Static):
    """代码/文件内容展示块 — 语法高亮 + 文件头 + 语言标签"""

    can_focus = True
    DEFAULT_CSS = """
    ArtifactWidget {
        height: auto;
        min-height: 1;
        margin: 0 0 1 0;
        padding: 0 1;
    }
    ArtifactWidget:focus {
        background: $surface;
    }
    """

    def __init__(
        self,
        content: str,
        language: str = "",
        title: str = "",
        stat_line: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._content = content
        self._language = language
        self._title = title
        self._stat_line = stat_line

    def render(self):
        parts: list[RenderableType] = []

        # 文件头
        header = Text("")
        if self._title:
            try:
                header = Text.from_markup(f"{self._title}")
            except Exception:
                header = Text(f"{self._title}")
        if self._language:
            header.append(f"  {self._language}", style="bold #5abf7a")
        if header:
            parts.append(header)

        # 统计信息（在代码块外面）
        if self._stat_line:
            parts.append(Text(f"  {self._stat_line}", style="dim"))

        # 代码内容
        if self._content.strip():
            lang = self._language or "text"
            try:
                syntax = Syntax(
                    self._content,
                    lang,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                    background_color="default",
                )
            except Exception:
                # 语言不支持时回退到纯文本
                syntax = Syntax(
                    self._content,
                    "text",
                    line_numbers=True,
                    word_wrap=True,
                    background_color="default",
                )
            parts.append(syntax)
        else:
            parts.append(Text("  (空)", style="dim"))

        return Group(*parts)

    @classmethod
    def detect_language(cls, filename: str) -> str:
        """根据文件名猜测语言"""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".jsx": "jsx",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".html": "html",
            ".css": "css",
            ".sh": "bash",
            ".bat": "batch",
            ".ps1": "powershell",
            ".sql": "sql",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".cfg": "ini",
            ".ini": "ini",
            ".conf": "ini",
            ".xml": "xml",
            ".yaml": "yaml",
            ".txt": "text",
        }
        import os.path
        ext = os.path.splitext(filename)[1].lower()
        return ext_map.get(ext, "text")
