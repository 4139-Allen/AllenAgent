"""
感知路由器
检测输入类型，分发到对应处理器
"""

import os
from pathlib import Path
from typing import Union

from schemas.context import PerceptionContext
from perception.text_handler import TextHandler


class PerceptionRouter:
    """
    感知路由器

    当前支持：
        - text: 纯文本输入

    扩展点：
        - file: 文件路径 → 读取后走 text_handler
        - image: 图片路径 → 未来接 vision API
        - stream: 数据流 → 未来接 stream handler
    """

    # 文件扩展名 → 处理方式
    TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.json', '.csv', '.xml', '.html', '.yaml', '.yml', '.toml'}

    def __init__(self, max_chars: int = 12000):
        self.text_handler = TextHandler(max_chars=max_chars)

    def process(self, user_input: str) -> PerceptionContext:
        """
        处理用户输入

        自动检测输入类型：
        - 看起来是文件路径 → 尝试读取文件
        - 其他 → 当纯文本处理
        """
        stripped = user_input.strip()

        # 检测是否是文件路径
        if self._looks_like_filepath(stripped):
            path = Path(stripped)
            if path.exists():
                return self._handle_file(path)

        # 默认：纯文本
        return self.text_handler.process(stripped)

    def _looks_like_filepath(self, text: str) -> bool:
        """判断文本是否像文件路径"""
        if len(text) > 500:
            return False
        if '\n' in text:
            return False
        # 包含路径分隔符或常见扩展名
        has_separator = '/' in text or '\\' in text
        has_extension = any(text.endswith(ext) for ext in self.TEXT_EXTENSIONS | {'.pdf', '.png', '.jpg', '.jpeg', '.gif'})
        return has_separator or has_extension

    def _handle_file(self, path: Path) -> PerceptionContext:
        """处理文件输入"""
        ext = path.suffix.lower()

        # 文本类文件
        if ext in self.TEXT_EXTENSIONS:
            try:
                content = path.read_text(encoding="utf-8")
                return self.text_handler.process(
                    content,
                    metadata={"source_file": str(path), "file_extension": ext},
                )
            except Exception as e:
                return PerceptionContext(
                    text=f"[读取文件失败: {e}]",
                    source_type="file",
                    metadata={"source_file": str(path), "error": str(e)},
                )

        # 未来扩展：图片、PDF 等
        return PerceptionContext(
            text=f"[暂不支持的文件类型: {ext}]",
            source_type="file",
            metadata={"source_file": str(path), "file_extension": ext},
        )
