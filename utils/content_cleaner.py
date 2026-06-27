"""工具结果内容清理器 — 去除 ANSI 转义码、多余空行"""
import re


def strip_tool_result_content(content: str) -> str:
    """清理工具返回内容：去除 ANSI 码、压缩空行"""
    if not content:
        return ""

    # 去除 ANSI 转义码
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    content = ansi_escape.sub('', content)

    # 压缩连续空行为最多一个
    content = re.sub(r'\n{3,}', '\n\n', content)

    # 去除首尾空白
    content = content.strip()

    return content
