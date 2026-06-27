"""事件渲染器 — 按文档设计，每个事件类型独立 Renderer

各 Renderer 通过 @register 装饰器自动注册到 RendererRegistry，
import 模块即可触发注册。
"""

from frontends.tui.renderers.base import BaseRenderer
from frontends.tui.renderers.registry import RendererRegistry, register

# import 模块触发 @register 装饰器
from frontends.tui.renderers import thinking
from frontends.tui.renderers import answer
from frontends.tui.renderers import subtask
from frontends.tui.renderers import feedback
from frontends.tui.renderers import file_change
from frontends.tui.renderers import confirm
from frontends.tui.renderers import artifact

__all__ = [
    "BaseRenderer", "RendererRegistry", "register",
]
