"""Renderer 注册表 — 事件类型 → Renderer 映射"""

from frontends.tui.renderers.base import BaseRenderer


class RendererRegistry:
    """全局注册表"""
    _registry: dict[str, BaseRenderer] = {}

    @classmethod
    def register(cls, event_type: str, renderer: BaseRenderer):
        cls._registry[event_type] = renderer

    @classmethod
    def get(cls, event_type: str) -> BaseRenderer | None:
        return cls._registry.get(event_type)

    @classmethod
    def render(cls, panel, event) -> bool:
        """渲染事件，返回是否找到对应 renderer"""
        renderer = cls.get(event.type)
        if renderer:
            renderer.render(panel, event)
            return True
        return False


def register(*event_types: str):
    """装饰器：将 Renderer 类注册到指定事件类型"""
    def decorator(cls):
        instance = cls()
        for et in event_types:
            RendererRegistry.register(et, instance)
        return cls
    return decorator
