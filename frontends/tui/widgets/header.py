"""极简顶部状态栏"""
from textual.widgets import Static
from textual.reactive import reactive


PULSE = ["◐", "◓", "◑", "◒"]


class HeaderBar(Static):
    """顶部状态栏 — 极简风格"""

    model_name: reactive[str] = reactive("DeepSeek-Chat")
    step_count: reactive[int] = reactive(0)

    def __init__(self, model_name: str = "DeepSeek-Chat", **kwargs):
        super().__init__(**kwargs)
        self.model_name = model_name
        self._busy = False
        self._pulse_idx = 0
        self._pulse_timer = None

    def render(self) -> str:
        if self._busy:
            pulse = PULSE[self._pulse_idx]
            activity = f"[bold cyan]{pulse}[/]"
        else:
            activity = "[dim]●[/]"
        return (
            f" Allen │ "
            f"{self.model_name} │ "
            f"steps:{self.step_count} │ "
            f"{activity}"
        )

    def set_busy(self, busy: bool):
        self._busy = busy
        if busy and not self._pulse_timer:
            self._pulse_timer = self.set_interval(0.15, self._tick)
        elif not busy and self._pulse_timer:
            self._pulse_timer.stop()
            self._pulse_timer = None
        self.refresh()

    def _tick(self):
        self._pulse_idx = (self._pulse_idx + 1) % len(PULSE)
        self.refresh()

    def update_model(self, name: str):
        self.model_name = name

    def update_steps(self, count: int):
        self.step_count = count
