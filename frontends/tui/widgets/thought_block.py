"""推理过程块"""
import time
from textual.widgets import Static
from rich.text import Text
from rich.console import Group


_TOOL_CALL_DOT = "● "  # black circle


class ThoughtBlock(Static):
    """推理过程块，包含思考和工具调用的完整转录。"""

    can_focus = True
    DEFAULT_CSS = """
    ThoughtBlock {
        height: auto;
        min-height: 1;
        margin: 0;
        padding: 0 1;
        color: $text;
    }
    ThoughtBlock:focus {
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._segments: list[tuple[str, str | None]] = []
        self._expanded = False
        self._done = False
        self._start_time = time.time()
        self._final_elapsed = 0
        self._is_paused = False
        self._paused_elapsed = 0
        self._timer = None
        self._blink_timer = None
        self._blink_idx = -1
        self._blink_state = 0
        self._subtask_idx = -1
        self._subtask_blink_timer = None
        self._subtask_blink_state = 0

    def on_mount(self):
        self._timer = self.set_interval(1, self._tick)

    def _tick(self):
        if self._done:
            if self._timer:
                self._timer.stop()
            return
        if not self._is_paused:
            self.refresh()

    def _current_elapsed(self) -> int:
        if self._done:
            return self._final_elapsed
        if self._is_paused:
            return max(1, self._paused_elapsed)
        return max(1, int(time.time() - self._start_time))

    def pause(self):
        if not self._is_paused and not self._done:
            self._paused_elapsed = int(time.time() - self._start_time)
            self._is_paused = True

    def resume(self):
        if self._is_paused and not self._done:
            paused_duration = time.time() - (self._start_time + self._paused_elapsed)
            self._start_time += paused_duration
            self._is_paused = False

    def render(self):
        elapsed = self._current_elapsed()
        title_style = "dim"
        preview_lines = 4

        def _render_seg(content: str, style: str | None, blink: bool = False) -> Text:
            """渲染单个段落：指示符上色（● ▶ ✓），其余文字 dim"""
            if not style or not content:
                return Text(content or "")
            first = content[0]
            if first in ("●", "▶", "✓"):
                # 子任务闪烁（黄色）
                if idx == self._subtask_idx and self._subtask_blink_timer:
                    c = "bold yellow" if self._subtask_blink_state == 0 else "dim #8a7a00"
                    return Text.from_markup(f"[{c}]●[/][dim]{content[1:]}[/]")
                # 工具调用闪烁（绿色）
                if blink:
                    if self._blink_state == 0:
                        return Text.from_markup(f"[bold #4caf50]●[/][dim]{content[1:]}[/]")
                    else:
                        return Text.from_markup(f"[dim #2a6a30]●[/][dim]{content[1:]}[/]")
                return Text.from_markup(f"[{style}]{first}[/][dim]{content[1:]}[/]")
            t = Text(content)
            t.stylize(style)
            return t

        if not self._done and not self._expanded:
            if not self._segments:
                return Text(f"推理过程 ({elapsed}s) (ctrl+o 展开)", style=title_style)
            parts = [Text(f"推理过程 ({elapsed}s)", style=title_style)]
            shown = 0
            for idx, (content, style) in enumerate(self._segments):
                if shown >= preview_lines:
                    break
                parts.append(_render_seg(content, style))
                shown += 1
            if len(self._segments) > preview_lines:
                parts.append(Text(f"... (ctrl+o 展开)", style="dim"))
            else:
                parts.append(Text("(ctrl+o 展开)", style="dim"))
            return Group(*parts)

        if self._done and not self._expanded:
            return Text(f"推理过程 {elapsed}s (ctrl+o 展开)", style=title_style)

        # expanded
        if self._done:
            parts = [Text("推理过程 (ctrl+o 折叠)", style=title_style)]
        else:
            parts = [Text(f"推理过程 ({elapsed}s)", style=title_style)]

        for idx, (content, style) in enumerate(self._segments):
            blink = (idx == self._blink_idx and self._blink_timer and style and "●" in content)
            parts.append(_render_seg(content, style, blink=blink))
        return Group(*parts)

    # ── streaming interface ──

    def append_thinking(self, token: str):
        if not token:
            return
        if self._segments and self._segments[-1][1] is None:
            prev_content, style = self._segments[-1]
            self._segments[-1] = (prev_content + token, None)
        else:
            self._segments.append((token, None))
        self.refresh(layout=True)

    def append_colored(self, text: str, color: str) -> int:
        """添加带颜色的文本行，返回该行在 _segments 中的索引"""
        idx = len(self._segments)
        self._segments.append((text, f"bold {color}"))
        self.refresh(layout=True)
        return idx

    def start_subtask(self, text: str):
        """添加闪烁黄点子任务指示行"""
        self._segments.append((f"● {text}", "bold yellow"))
        self._subtask_idx = len(self._segments) - 1
        self._subtask_blink_state = 0
        self._start_subtask_blink()
        self.refresh(layout=True)

    def done_subtask(self):
        """子任务完成：● 变 ✓，停止闪烁"""
        self._stop_subtask_blink()
        if 0 <= self._subtask_idx < len(self._segments):
            content, style = self._segments[self._subtask_idx]
            self._segments[self._subtask_idx] = ("✓" + content[1:], "bold green")
        self.refresh(layout=True)

    def _start_subtask_blink(self):
        self._stop_subtask_blink()
        self._subtask_blink_state = 0
        self._subtask_blink_timer = self.set_interval(0.5, self._subtask_blink_tick)

    def _stop_subtask_blink(self):
        if self._subtask_blink_timer:
            try:
                self._subtask_blink_timer.stop()
            except Exception:
                pass
            self._subtask_blink_timer = None

    def _subtask_blink_tick(self):
        self._subtask_blink_state = 1 - self._subtask_blink_state
        self.refresh()

    def add_tool_call_line(self, text: str):
        """add a tool call line (green dot, blinking)"""
        self._segments.append((f"{_TOOL_CALL_DOT}{text}", "bold #4caf50"))
        self._blink_idx = len(self._segments) - 1
        self._start_blink()
        self.refresh(layout=True)

    def finalize_tool_call(self):
        """tool done: stop blink, dot turns orange"""
        self._stop_blink()
        if 0 <= self._blink_idx < len(self._segments):
            content, _ = self._segments[self._blink_idx]
            self._segments[self._blink_idx] = (content, "bold #ff8c00")
        self._blink_idx = -1
        self.refresh(layout=True)

    def add_tool_result_line(self, text: str):
        """add a tool result line (blue dot)"""
        self._segments.append((f"{_TOOL_CALL_DOT}{text}", "bold #4a9eff"))
        self.refresh(layout=True)

    def _start_blink(self):
        self._stop_blink()
        self._blink_state = 0
        self._blink_timer = self.set_interval(0.5, self._blink_tick)

    def _stop_blink(self):
        if self._blink_timer:
            try:
                self._blink_timer.stop()
            except Exception:
                pass
            self._blink_timer = None

    def _blink_tick(self):
        self._blink_state = 1 - self._blink_state
        self.refresh()

    def set_segments(self, segments: list[tuple[str, str | None]]):
        self._segments = list(segments)
        self._blink_idx = -1
        self._stop_blink()

    def finish(self, elapsed: int | None = None):
        self._stop_blink()
        self._stop_subtask_blink()
        if elapsed is not None:
            self._final_elapsed = elapsed
        elif not self._final_elapsed:
            self._final_elapsed = max(1, int(time.time() - self._start_time))
        self._done = True
        if self._timer:
            self._timer.stop()
        self.refresh(layout=True)

    def set_elapsed(self, elapsed: int):
        self._final_elapsed = elapsed
        self.refresh()

    def toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.focus()
            self.scroll_visible(top=True)
        self.refresh(layout=True)
