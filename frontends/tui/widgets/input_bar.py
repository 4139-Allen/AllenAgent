"""底部输入区 — Enter 发送，Ctrl+J 换行"""
from rich.cells import cell_len
from textual.widgets import Static, TextArea, OptionList
from textual.widgets.option_list import Option
from textual.widgets.text_area import Edit
from textual.containers import Horizontal
from textual.message import Message
from textual import events
from frontends.shared.commands import get_tui_commands, get_command_names
from frontends.tui.widgets.status_bar import StatusBar


class AllenTextArea(TextArea):
    """自定义 TextArea — Enter 发送，不插入换行"""

    class Submitted(Message):
        """被按下"""
        def __init__(self, text: str):
            super().__init__()
            self.text = text

    def action_undo(self) -> None:
        """安全撤销：先校正光标位置，防 Textual 内部越界崩溃"""
        try:
            super().action_undo()
        except ValueError:
            # 撤销后文档行数减少，光标位置可能越界 → 重置到末尾
            try:
                self.cursor_location = (0, 0)
                self.action_undo()
            except Exception:
                pass

    def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            # Enter = 发送（拦截，不插入换行）
            event.stop()
            event.prevent_default()
            text = self.text.strip()
            if text:
                self.post_message(self.Submitted(text))
                self.clear()
            return
        if event.key == "ctrl+j":
            # Ctrl+J = 插入换行
            event.stop()
            loc = self.cursor_location
            self.edit(Edit("\n", loc, loc, False))
            return
        super()._on_key(event)


class InputBar(Static):
    """底部输入区"""

    DEFAULT_CSS = """
    InputBar {
        dock: bottom;
        height: auto;
        min-height: 3;
        max-height: 22;
        background: $surface;
        margin: 0;
        padding: 0;
        scrollbar-size: 0 0;
    }
    #border-top, #border-bottom {
        height: 1;
        color: $text-muted;
        margin: 0;
        padding: 0;
    }
    #input-row {
        height: 1;
        min-height: 1;
        margin: 0;
        padding: 0;
        align: left top;
    }
    #prompt-char {
        width: 2;
        min-width: 2;
        height: 1;
        color: $text-muted;
        margin: 0;
        padding: 0;
    }
    #main-input {
        height: 1;
        border: none;
        background: $surface;
        padding: 0 1;
        margin: 0;
    }
    #main-input:focus {
        border: none;
    }
    #cmd-list {
        height: auto;
        max-height: 8;
        background: $surface;
        border: none;
        margin: 0;
        padding: 0;
        scrollbar-size: 0 0;
    }
    #cmd-list > .option-list--option {
        padding: 0 2;
    }
    #cmd-list:focus .option-list--option-highlighted {
        background: transparent;
        color: #64b5f6;
    }
    #cmd-list .option-list--option-highlighted {
        background: transparent;
        color: #64b5f6;
    }
    """

    class Submitted(Message):
        def __init__(self, value: str):
            super().__init__()
            self.value = value

    class CommandSelected(Message):
        def __init__(self, command: str):
            super().__init__()
            self.command = command

    class HistorySelected(Message):
        def __init__(self, conversation: dict):
            super().__init__()
            self.conversation = conversation

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._history: list[str] = []
        self._history_idx: int = -1
        self._current_input: str = ""

    def compose(self):
        yield Static("─" * 500, id="border-top")
        with Horizontal(id="input-row"):
            yield Static("❯", id="prompt-char")
            yield AllenTextArea(id="main-input")
        yield Static("─" * 500, id="border-bottom")
        yield StatusBar(id="status-bar")

    def on_mount(self):
        inp = self.query_one("#main-input")
        inp.show_line_numbers = False
        inp.soft_wrap = True

    def on_allen_text_area_submitted(self, event: AllenTextArea.Submitted):
        """处理 Enter 发送"""
        value = event.text
        if value:
            self._add_history(value)
            self.post_message(self.Submitted(value))
        self._hide_commands()

    def show_commands(self, filter_text: str = ""):
        """显示命令列表（内联）"""
        try:
            cmd_list = self.query_one("#cmd-list")
        except Exception:
            cmd_list = None

        cmds = get_tui_commands()
        # 与历史列表一致，说明左对齐到同一列
        max_cmd_width = max(cell_len(c.name) for c in cmds) if cmds else 0
        fixed_col = max_cmd_width + 4  # 命令名宽度 + 4空格间隔
        filtered = []
        for c in cmds:
            if not c.name.startswith(filter_text.lower().strip()):
                continue
            pad = max(fixed_col - cell_len(c.name), 2)
            label = f"  {c.name}{' ' * pad}{c.desc}"
            filtered.append(Option(label, id=c.name))

        if not filtered:
            self._hide_commands()
            return

        if cmd_list is None:
            cmd_list = OptionList(id="cmd-list")
            self.mount(cmd_list)

        cmd_list.clear_options()
        cmd_list.add_options(filtered)
        # 隐藏状态栏
        try:
            self.query_one("#status-bar").display = False
        except Exception:
            pass

    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f}KB"
        else:
            return f"{size/1024/1024:.1f}MB"

    def show_history(self, conversations: list[dict]):
        """显示历史对话列表（内联）"""
        self._hide_commands()
        if not conversations:
            return

        self._history_conversations = conversations
        # 先确定右侧信息（日期+大小）的最大视觉宽度
        meta_list = []
        max_meta_width = 0
        for c in conversations[:20]:
            created = c.get('created_at', '')
            file_size = c.get('file_size', 0)
            date_str = created.split(" ")[0] if " " in created else created[:10]
            size_str = self._format_size(file_size)
            meta = f"{date_str}  {size_str}"
            meta_list.append(meta)
            max_meta_width = max(max_meta_width, cell_len(meta))

        options = []
        for i, c in enumerate(conversations[:20]):
            title = c.get('title', c['id'][:20])
            meta = meta_list[i]
            # 填充宽度 = 总宽度 - 左侧缩进(2) - meta宽度 - 间隔(1)
            fill = 56 - max_meta_width - 3
            display = ""
            for ch in title:
                if cell_len(display + ch) > fill:
                    display += "..."
                    break
                display += ch
            pad = fill - cell_len(display)
            label = f"  {display}{' ' * pad} {meta}"
            options.append(Option(label, id=str(i)))

        cmd_list = OptionList(id="cmd-list")
        self.mount(cmd_list)
        cmd_list.clear_options()
        cmd_list.add_options(options)
        # 隐藏状态栏
        try:
            self.query_one("#status-bar").display = False
        except Exception:
            pass

    def _hide_commands(self):
        """隐藏命令/历史列表"""
        try:
            cmd_list = self.query_one("#cmd-list")
            cmd_list.remove()
        except Exception:
            pass
        # 恢复状态栏
        try:
            self.query_one("#status-bar").display = True
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        """选项被选中"""
        if event.option_list.id == "cmd-list":
            option_id = event.option_id
            if hasattr(self, '_history_conversations') and option_id.isdigit():
                idx = int(option_id)
                if 0 <= idx < len(self._history_conversations):
                    self.post_message(self.HistorySelected(self._history_conversations[idx]))
            else:
                inp = self.query_one("#main-input")
                inp.load_text(option_id + " ")
                self.post_message(self.CommandSelected(option_id))
            inp = self.query_one("#main-input")
            inp.focus()
            self._hide_commands()

    def on_key(self, event):
        inp = self.query_one("#main-input")

        if event.key == "escape":
            self._hide_commands()
            inp.focus()
            return

        # 当命令列表显示时，上下键用来选择命令
        try:
            cmd_list = self.query_one("#cmd-list")
        except Exception:
            cmd_list = None

        if cmd_list and event.key in ("up", "down"):
            cmd_list.focus()
            if event.key == "up":
                cmd_list.action_cursor_up()
            else:
                cmd_list.action_cursor_down()
            event.stop()
            return

        if event.key == "up":
            if not self._history:
                return
            if self._history_idx == -1:
                self._current_input = inp.text
                self._history_idx = len(self._history) - 1
            elif self._history_idx > 0:
                self._history_idx -= 1
            else:
                return
            inp.load_text(self._history[self._history_idx])
            event.stop()
            return

        if event.key == "down":
            if self._history_idx == -1:
                return
            if self._history_idx < len(self._history) - 1:
                self._history_idx += 1
                inp.load_text(self._history[self._history_idx])
            else:
                self._history_idx = -1
                inp.load_text(self._current_input)
            event.stop()
            return

        if event.key == "tab":
            value = inp.text
            if value.startswith("/"):
                cmd_names = get_command_names("tui")
                matches = [c for c in cmd_names if c.startswith(value)]
                if len(matches) == 1:
                    inp.load_text(matches[0] + " ")
                    event.stop()
                elif len(matches) > 1:
                    prefix = matches[0]
                    for m in matches[1:]:
                        while not m.startswith(prefix):
                            prefix = prefix[:-1]
                    if len(prefix) > len(value):
                        inp.load_text(prefix)
                    event.stop()
            return

    def _add_history(self, value: str):
        if not self._history or self._history[-1] != value:
            self._history.append(value)
        self._history_idx = -1
        self._current_input = ""

    def focus_input(self):
        self.query_one("#main-input").focus()
