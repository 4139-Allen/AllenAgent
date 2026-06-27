"""
底部状态栏 — 显示模型、上下文进度条、对话时长
实时刷新，每 1 秒更新一次
数据自动从父级 ChatScreen 获取，无需手动 set
"""

from datetime import datetime
from pathlib import Path
from textual.widgets import Static
from textual.timer import Timer
from rich.markup import escape as rich_escape
from utils.token_counter import estimate_tokens

_CONTEXT_LOAD_RATIO = 0.95

BAR_WIDTH = 20


def _progress_bar(pct: float, width: int = BAR_WIDTH) -> str:
    """绘制进度条 ████░░░░"""
    filled = round(pct / 100 * width)
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


class StatusBar(Static):
    """底部状态栏 — dock 在输入框下方，显示模型/上下文/时长"""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 2;
    }
    """

    def __init__(self, model_manager=None, agent=None, session_start=None, **kwargs):
        super().__init__("", **kwargs)
        self._status_mm = model_manager
        self._status_agent = agent
        self._session_start = session_start or datetime.now()
        self._timer: Timer | None = None

    def on_mount(self):
        self._timer = self.set_interval(1, self._refresh)
        self._cached_sys_prompt = ""  # 缓存系统提示词
        self._cached_memory_hash = 0  # 记录 memory 哈希
        self._cached_tokens = 0       # 缓存 token 数
        self._refresh()

    def on_unmount(self):
        if self._timer:
            self._timer.stop()

    # ── 数据源 ──────────────────────────

    def set_model_manager(self, mm):
        self._status_mm = mm

    def set_agent(self, agent):
        self._status_agent = agent

    # ── 渲染 ────────────────────────────

    def _context_color(self, pct: float) -> str:
        if pct >= 95:
            return "#ff6b6b"
        if pct >= 80:
            return "#ffd93d"
        if pct >= 30:
            return "#4a9eff"
        return "#4caf50"

    def _refresh(self):
        try:
            self._last_pct = 0
            context_part = self._format_context()
            # 从 context 字符串中提取百分比用于着色
            parts = [
                self._format_model(),
                self._format_folder(),
                context_part,
                self._format_duration(),
            ]
            self.update("  │  ".join(parts))
        except Exception:
            self.update("...")

    def _get_model_name(self) -> str:
        mm = self._status_mm
        if not mm:
            return "?"
        try:
            model_id = mm.current_model
            mc = mm.config.get_model_config(model_id)
            return mc.name if mc else model_id
        except Exception:
            return "?"

    def _format_model(self) -> str:
        name = self._get_model_name()
        return f"[dim]Model: [dim]\\[{rich_escape(name)}]"

    def _format_folder(self) -> str:
        return Path.cwd().name

    def _format_context(self) -> str:
        agent = self._status_agent
        mm = self._status_mm
        if not agent or not mm:
            return "Context ░░░░░░░░░░  --"
        try:
            # 缓存系统提示词（每秒都重算太浪费）
            if not self._cached_sys_prompt:
                try:
                    self._cached_sys_prompt = agent._build_system_prompt()
                except Exception:
                    self._cached_sys_prompt = ""

            # 检查 memory 是否变化
            messages = agent.memory.get_messages() if agent.memory else []
            current_hash = hash(str(messages)) if messages else 0

            if current_hash != self._cached_memory_hash or not self._cached_tokens:
                # 重新计算 token
                text_parts = [self._cached_sys_prompt]
                for m in messages:
                    content = m.get("content")
                    if content:
                        text_parts.append(str(content))
                    for tc in m.get("tool_calls", []):
                        text_parts.append(str(tc.get("function", {}).get("arguments", "")))

                all_text = "\n".join(text_parts)
                self._cached_tokens = estimate_tokens(all_text)
                self._cached_memory_hash = current_hash

            tokens = self._cached_tokens

            # 取 context_window
            try:
                mc = mm.config.get_model_config(mm.current_model)
                ctx_window = mc.context_window if mc else 128000
            except Exception:
                ctx_window = 128000

            effective_max = ctx_window * _CONTEXT_LOAD_RATIO
            pct = min(tokens / effective_max * 100, 100) if effective_max else 0
            self._last_pct = pct
            bar = _progress_bar(pct)
            color = self._context_color(pct)

            # 从 agent 获取最新的 token 消耗
            usage = agent._stream_usage if hasattr(agent, '_stream_usage') else {}
            completion_tokens = usage.get("completion_tokens", 0)

            def _fmt(n):
                return f"{n/1000:.1f}k" if n >= 1000 else str(n)

            if completion_tokens > 0:
                return f"Context [{color}]{bar} {pct:.0f}% ({_fmt(tokens)}  +{_fmt(completion_tokens)})[/]"
            return f"Context [{color}]{bar} {pct:.0f}% ({_fmt(tokens)})[/]"
        except Exception:
            return "Context ░░░░░░░░░░  --"

    def _format_duration(self) -> str:
        elapsed = datetime.now() - self._session_start
        total_minutes = max(int(elapsed.total_seconds() // 60), 1)
        h, m = divmod(total_minutes, 60)
        if h:
            return f"⏱ {h}h {m}m"
        return f"⏱ {m}m"
