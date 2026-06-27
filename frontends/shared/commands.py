"""统一命令注册表 — TUI 和 CLI 共用"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class CommandDef:
    """命令定义"""
    name: str           # /help
    desc: str           # 帮助
    tui: bool = True    # TUI 可用
    cli: bool = True    # CLI 可用


# 所有命令定义（单一来源）
COMMAND_DEFS: list[CommandDef] = [
    CommandDef("/help",     "帮助",     tui=True,  cli=True),
    CommandDef("/clear",    "清屏",     tui=True,  cli=False),
    CommandDef("/compress","压缩上下文",tui=True,  cli=False),
    CommandDef("/new",      "新对话",   tui=True,  cli=True),
    CommandDef("/history",  "历史",     tui=True,  cli=False),
    CommandDef("/load",     "加载 N",   tui=True,  cli=True),
    CommandDef("/save",     "保存",     tui=True,  cli=True),
    CommandDef("/delete",   "删除 N",   tui=True,  cli=True),
    CommandDef("/model",    "模型 NAME",tui=True,  cli=True),
    CommandDef("/status",   "状态",     tui=True,  cli=False),
    CommandDef("/theme",    "切换暗色/亮色", tui=True,  cli=False),
    CommandDef("/exit",     "退出",     tui=True,  cli=False),
    CommandDef("/memory",   "记忆",     tui=False, cli=True),
    CommandDef("/remember", "记住 TEXT",tui=False, cli=True),
]


def get_tui_commands() -> list[CommandDef]:
    """返回 TUI 可用命令"""
    return [c for c in COMMAND_DEFS if c.tui]


def get_cli_commands() -> list[CommandDef]:
    """返回 CLI 可用命令"""
    return [c for c in COMMAND_DEFS if c.cli]


def get_command_names(mode: str = "tui") -> list[str]:
    """返回命令名称列表（用于补全）"""
    cmds = get_tui_commands() if mode == "tui" else get_cli_commands()
    return [c.name for c in cmds]


def get_help_text(mode: str = "tui") -> str:
    """返回帮助文本"""
    cmds = get_tui_commands() if mode == "tui" else get_cli_commands()
    lines = [f"  {c.name}\t{c.desc}" for c in cmds]
    return "\n".join(lines)


def find_command(text: str, mode: str = "tui") -> Optional[CommandDef]:
    """根据输入查找匹配的命令"""
    cmds = get_tui_commands() if mode == "tui" else get_cli_commands()
    text = text.strip().lower()
    for c in cmds:
        if c.name == text or text.startswith(c.name + " "):
            return c
    return None
