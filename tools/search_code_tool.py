"""
项目代码搜索工具
Agent 可通过此工具搜索项目中的代码文件，而不需要走 shell。

三个操作：
  grep  — 按内容搜索（正则匹配）
  glob  — 按文件名搜索（通配符）
  tree  — 查看目录结构

用法示例：
  code_search(action="grep", pattern="def execute", path="tools", include="*.py", context=2)
  code_search(action="glob", pattern="**/*.jsonl")
  code_search(action="tree", path=".", depth=2)
"""

import os
import re
import fnmatch
from pathlib import Path
from tools.base import BaseTool
from schemas.tool import ToolResult

# ── 默认跳过的目录 ──────────────────────────
IGNORE_DIRS = {
    ".venv", "__pycache__", ".git", "node_modules",
    ".pytest_cache", ".egg-info", "dist", "build",
    ".claude", ".mypy_cache", ".tox", "env",
    ".idea", ".vscode", ".github",
}

# ── 二进制后缀（跳过，不读内容）─────────────
BINARY_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib",
    ".exe", ".msi", ".bin", ".o", ".a", ".lib",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".flac",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".sqlite3",
    ".lock", ".sum",
}

# ── 搜索上限 ───────────────────────────────
MAX_GREP_RESULTS = 50    # grep 最大结果条数
MAX_GREP_LINES_PER_FILE = 20  # 每个文件最多匹配行数
MAX_GLOB_RESULTS = 100   # glob 最大结果数
MAX_TREE_ENTRIES = 200   # tree 最大条目数
MAX_FILE_SIZE = 512 * 1024  # 跳过 >512KB 的文件


class CodeSearchTool(BaseTool):
    """
    项目代码搜索工具
    搜索文件内容（grep）、文件名（glob）、目录结构（tree）
    """

    def __init__(self):
        super().__init__(
            name="code_search",
            description=(
                "搜索项目代码文件。三个操作："
                "grep — 按文件内容搜索（正则匹配），"
                "glob — 按文件名搜索（通配符如 **/*.py），"
                "tree — 查看目录结构。"
                "适用于查找函数定义、引用、配置文件位置等场景。"
            )
        )

    def execute(self, action: str = None, pattern: str = None, path: str = ".",
                include: str = None, exclude: str = None,
                context: int = 0, depth: int = 2, **kwargs) -> ToolResult:
        """
        执行搜索操作

        Args:
            action: 操作类型 (grep/glob/tree)
            pattern: 搜索模式（grep用正则，glob用通配符）
            path: 搜索路径，默认当前目录
            include: 文件通配符过滤（如 "*.py"），仅 grep 有效
            exclude: 排除的通配符（如 "*.min.js"）
            context: 匹配行上下文的行数，仅 grep 有效
            depth: tree 的递归深度，默认 2
        """
        if not action:
            return ToolResult(
                success=False, data=None,
                error="请指定操作类型: grep, glob 或 tree",
                source="code_search",
            )

        try:
            if action == "grep":
                if not pattern:
                    return ToolResult(
                        success=False, data=None,
                        error="grep 需要 pattern 参数",
                        source="code_search",
                    )
                return self._grep(pattern, path, include, exclude, context)

            elif action == "glob":
                if not pattern:
                    return ToolResult(
                        success=False, data=None,
                        error="glob 需要 pattern 参数",
                        source="code_search",
                    )
                return self._glob(pattern, path, exclude)

            elif action == "tree":
                return self._tree(path, depth, exclude)

            else:
                return ToolResult(
                    success=False, data=None,
                    error=f"不支持的操作: {action}，请用 grep、glob 或 tree",
                    source="code_search",
                )

        except Exception as e:
            return ToolResult(
                success=False, data=None,
                error=f"搜索失败: {e}",
                source="code_search",
            )

    # ── grep：文件内容搜索 ──────────────────────

    def _grep(self, pattern: str, root_path: str, include: str | None,
              exclude: str | None, context_lines: int) -> ToolResult:
        root = Path(root_path).resolve()
        if not root.exists():
            return ToolResult(
                success=False, data=None,
                error=f"路径不存在: {root_path}",
                source="code_search",
            )
        if not root.is_dir():
            root = root.parent

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(
                success=False, data=None,
                error=f"无效的正则表达式: {e}",
                source="code_search",
            )

        results = []
        total_matches = 0
        file_count = 0

        for filepath in self._iter_files(root, include, exclude):
            if total_matches >= MAX_GREP_RESULTS:
                break

            matches = self._search_file(filepath, regex, context_lines)
            if not matches:
                continue

            file_count += 1
            for match in matches:
                results.append({
                    "file": str(filepath.relative_to(root)),
                    "line": match["line"],
                    "content": match["content"],
                })
                total_matches += 1
                if total_matches >= MAX_GREP_RESULTS:
                    break

        if not results:
            return ToolResult(
                success=True,
                data={"action": "grep", "pattern": pattern, "results": [], "total": 0},
                source="code_search",
            )

        # 构建输出文本
        output_lines = []
        current_file = None
        for r in results:
            if r["file"] != current_file:
                output_lines.append(f"")
                output_lines.append(f"{r['file']}:")
                current_file = r["file"]
            output_lines.append(f"  {r['line']}: {r['content']}")

        return ToolResult(
            success=True,
            data={
                "action": "grep",
                "pattern": pattern,
                "results": results,
                "total": total_matches,
                "files": file_count,
                "text": "\n".join(output_lines).strip(),
            },
            source="code_search",
        )

    def _search_file(self, filepath: Path, regex: re.Pattern,
                     context_lines: int) -> list[dict]:
        """在单个文件中搜索匹配行"""
        # 跳过过大的文件
        try:
            if filepath.stat().st_size > MAX_FILE_SIZE:
                return []
        except OSError:
            return []

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []

        lines = text.splitlines()
        matches = []
        match_count = 0

        for i, line in enumerate(lines):
            if match_count >= MAX_GREP_LINES_PER_FILE:
                break
            if regex.search(line):
                if context_lines > 0:
                    # 带上下文
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)
                    ctx_lines = []
                    for j in range(start, end):
                        prefix = ">" if j == i else " "
                        ctx_lines.append(f"{prefix} {j+1}: {lines[j]}")
                    content = "\n".join(ctx_lines)
                else:
                    content = line
                matches.append({"line": i + 1, "content": content})
                match_count += 1

        return matches

    # ── glob：文件名搜索 ────────────────────────

    def _glob(self, pattern: str, root_path: str,
              exclude: str | None) -> ToolResult:
        root = Path(root_path).resolve()
        if not root.exists():
            return ToolResult(
                success=False, data=None,
                error=f"路径不存在: {root_path}",
                source="code_search",
            )

        # 用 Path.rglob 匹配
        # 将模式拆分为基路径和通配部分
        matched = []
        try:
            for filepath in root.rglob(pattern):
                if len(matched) >= MAX_GLOB_RESULTS:
                    break
                rel = filepath.relative_to(root)

                # 排除二进制（非纯文本文件）
                if filepath.suffix.lower() in BINARY_EXTENSIONS:
                    continue

                # 跳过忽略目录中的文件
                if any(part in IGNORE_DIRS for part in filepath.parts):
                    continue

                # 应用 exclude 过滤
                if exclude and fnmatch.fnmatch(str(rel), exclude):
                    continue

                # 标记是否为目录
                entry = str(rel)
                if filepath.is_dir():
                    entry += "/"

                matched.append(entry)

                # 如果是目录，限制数量避免爆炸
                if filepath.is_dir() and len(matched) >= 50:
                    break
        except Exception:
            pass

        if not matched:
            return ToolResult(
                success=True,
                data={"action": "glob", "pattern": pattern, "results": [], "total": 0},
                source="code_search",
            )

        return ToolResult(
            success=True,
            data={
                "action": "glob",
                "pattern": pattern,
                "results": matched,
                "total": len(matched),
                "text": "\n".join(matched),
            },
            source="code_search",
        )

    # ── tree：目录结构 ──────────────────────────

    def _tree(self, root_path: str, depth: int,
              exclude: str | None) -> ToolResult:
        root = Path(root_path).resolve()
        if not root.exists():
            return ToolResult(
                success=False, data=None,
                error=f"路径不存在: {root_path}",
                source="code_search",
            )
        if not root.is_dir():
            root = root.parent

        entries = []
        self._walk_tree(root, root, depth, exclude, entries, "")

        if not entries:
            return ToolResult(
                success=True,
                data={"action": "tree", "path": str(root), "results": [], "total": 0},
                source="code_search",
            )

        return ToolResult(
            success=True,
            data={
                "action": "tree",
                "path": str(root),
                "results": entries,
                "total": len(entries),
                "text": "\n".join(entries),
            },
            source="code_search",
        )

    def _walk_tree(self, root: Path, current: Path, max_depth: int,
                   exclude: str | None, entries: list, prefix: str):
        """递归遍历目录结构"""
        if len(entries) >= MAX_TREE_ENTRIES:
            return

        try:
            items = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        except PermissionError:
            entries.append(f"{prefix}[权限不足]")
            return

        for i, item in enumerate(items):
            if len(entries) >= MAX_TREE_ENTRIES:
                break

            rel = item.relative_to(root)

            # 跳过忽略目录
            if item.is_dir() and item.name in IGNORE_DIRS:
                continue

            # 跳过 exclude 模式
            if exclude and fnmatch.fnmatch(str(rel), exclude):
                continue

            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            display = f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}"
            entries.append(display)

            if item.is_dir() and max_depth > 1:
                extension = "    " if is_last else "│   "
                self._walk_tree(root, item, max_depth - 1, exclude, entries,
                               prefix + extension)

    # ── 辅助方法 ────────────────────────────────

    def _iter_files(self, root: Path, include: str | None,
                    exclude: str | None):
        """遍历目录，逐个返回匹配的文件"""
        for filepath in root.rglob("*"):
            if not filepath.is_file():
                continue

            # 跳过忽略目录中的文件
            if any(part in IGNORE_DIRS for part in filepath.parts):
                continue

            # 跳过二进制文件
            if filepath.suffix.lower() in BINARY_EXTENSIONS:
                continue

            # 跳过过大文件
            try:
                if filepath.stat().st_size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            rel = str(filepath.relative_to(root))

            # 应用 include 过滤
            if include:
                if not fnmatch.fnmatch(str(filepath.name), include) and \
                   not fnmatch.fnmatch(rel, include):
                    continue

            # 应用 exclude 过滤
            if exclude and fnmatch.fnmatch(rel, exclude):
                continue

            yield filepath

    # ── Schema ───────────────────────────────────

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["grep", "glob", "tree"],
                    "description": "操作类型：grep（内容搜索），glob（文件名搜索），tree（目录结构）"
                },
                "pattern": {
                    "type": "string",
                    "description": "搜索模式：grep 用正则表达式，glob 用通配符（如 **/*.py, *.jsonl）"
                },
                "path": {
                    "type": "string",
                    "description": "搜索路径，默认为当前目录 '.'",
                    "default": "."
                },
                "include": {
                    "type": "string",
                    "description": "文件类型过滤（通配符），如 '*.py'、'*.{ts,tsx}'。仅 grep 有效。"
                },
                "exclude": {
                    "type": "string",
                    "description": "排除模式（通配符），如 '*.min.js'、'*test*'"
                },
                "context": {
                    "type": "integer",
                    "description": "匹配行的上下文的行数，默认 0。仅 grep 有效。",
                    "default": 0
                },
                "depth": {
                    "type": "integer",
                    "description": "tree 的递归深度，默认 2",
                    "default": 2
                },
            },
            "required": ["action"],
        }
