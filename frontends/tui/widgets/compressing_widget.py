"""压缩进度组件 — 旋转动画 + 计时"""
import time
from textual.widgets import Static
from textual.timer import Timer


class CompressingWidget(Static):
    """压缩进度指示器 — 显示旋转动画和耗时"""

    DEFAULT_CSS = """
    CompressingWidget {
        height: auto;
        min-height: 1;
        margin: 0;
        padding: 0 1;
        color: #ffd93d;
    }
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, **kwargs):
        super().__init__("", **kwargs)
        self._start_time = time.time()
        self._frame = 0
        self._timer: Timer | None = None

    def on_mount(self):
        self._timer = self.set_interval(0.1, self._tick)

    def on_unmount(self):
        if self._timer:
            self._timer.stop()

    def _tick(self):
        self._frame = (self._frame + 1) % len(self.FRAMES)
        elapsed = max(1, int(time.time() - self._start_time))
        self.update(f"  {self.FRAMES[self._frame]} 压缩中... ({elapsed}s)")
