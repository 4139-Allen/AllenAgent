"""
文件读写工具
Agent 可通过此工具读取或写入本地文件
"""

import os
from pathlib import Path
from tools.base import BaseTool
from schemas.tool import ToolResult

# 项目根目录（用于判断是否写到项目外）
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class FileTool(BaseTool):
    """
    文件读写工具
    读取文件内容、创建新文件、追加内容
    """

    def __init__(self):
        super().__init__(
            name="file_io",
            description="读取/写入文件、列出目录内容、批量删除文件。列目录用 action=list 传入目录路径；查看文件内容用 action=read；删除用 action=delete。"
        )

    def execute(self, action: str, filepath: str = None, filepaths: list = None, content: str = None, **kwargs) -> ToolResult:
        if action == "read":
            return self._read(filepath)
        elif action == "list":
            return self._read(filepath)  # read 已支持目录列出
        elif action == "write":
            return self._write(filepath, content)
        elif action == "delete":
            paths = self._resolve_paths(filepath, filepaths)
            if not paths:
                return ToolResult(
                    success=False, data=None,
                    error="请提供 filepath 或 filepaths 参数",
                    source="file_io",
                )
            return self._batch_delete(paths)
        else:
            return ToolResult(
                success=False, data=None,
                error=f"不支持的操作: {action}，请用 read、write、list 或 delete",
                source="file_io",
            )

    def _resolve_paths(self, filepath: str = None, filepaths: list = None) -> list[str]:
        """合并 filepath 和 filepaths 为一个列表"""
        result = []
        if filepath:
            result.append(filepath)
        if filepaths:
            if isinstance(filepaths, list):
                result.extend(filepaths)
            elif isinstance(filepaths, str):
                result.append(filepaths)
        return result

    def _read(self, filepath: str) -> ToolResult:
        path = Path(filepath)

        if not path.exists():
            return ToolResult(success=False, data=None, error=f"文件不存在: {filepath}", source="file_io")

        # 目录：列出内容
        if path.is_dir():
            entries = []
            for item in sorted(path.iterdir()):
                prefix = "[DIR] " if item.is_dir() else "      "
                entries.append(f"{prefix}{item.name}")
            return ToolResult(
                success=True,
                data={"filepath": str(path), "type": "directory", "entries": entries},
                source="file_io",
            )

        # 文件：读取内容
        try:
            content = path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                data={"filepath": str(path), "type": "file", "content": content, "size": len(content)},
                source="file_io",
            )
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e), source="file_io")

    def _write(self, filepath: str, content: str) -> ToolResult:
        if content is None:
            return ToolResult(success=False, data=None, error="写入时 content 不能为空", source="file_io")

        path = Path(filepath)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                data={"filepath": str(path), "size": len(content)},
                source="file_io",
            )
        except PermissionError:
            return ToolResult(success=False, data=None, error=f"权限不足，无法写入: {filepath}", source="file_io")
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e), source="file_io")

    def _batch_delete(self, paths: list[str]) -> ToolResult:
        """批量删除多个文件"""
        results = []
        errors = []

        for filepath in paths:
            path = Path(filepath)
            if not path.exists():
                errors.append(f"{filepath}: 不存在")
                continue
            try:
                if path.is_dir():
                    import shutil
                    shutil.rmtree(path)
                else:
                    path.unlink()
                results.append(filepath)
            except PermissionError:
                errors.append(f"{filepath}: 权限不足")
            except Exception as e:
                errors.append(f"{filepath}: {e}")

        data = {
            "deleted": results,
            "count": len(results),
        }
        if errors:
            data["errors"] = errors

        return ToolResult(
            success=len(errors) == 0 or len(results) > 0,
            data=data,
            error="; ".join(errors) if errors else None,
            source="file_io",
        )

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete"],
                    "description": "操作类型：read 读取文件内容，write 写入文件，list 列出目录内容，delete 删除文件（支持批量）"
                },
                "filepath": {
                    "type": "string",
                    "description": "文件路径（与 filepaths 二选一，单个文件操作时使用）"
                },
                "filepaths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "文件路径列表（与 filepath 二选一，批量删除时使用）"
                },
                "content": {
                    "type": "string",
                    "description": "写入的内容（action=write 时必填）"
                },
            },
            "required": ["action"],
        }
