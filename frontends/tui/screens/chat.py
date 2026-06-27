"""
主聊天屏幕 — 布局 + 事件路由
厚重逻辑已分离到 chat_state.py（状态/命令）和 stream_handler.py（流式处理）
"""

import asyncio
import time
from textual.screen import Screen
from textual.widgets import OptionList, Static

from frontends.tui.widgets.chat_panel import ChatPanel
from frontends.tui.widgets.input_bar import InputBar
from frontends.tui.widgets.confirm_widget import ConfirmWidget
from frontends.tui.screens.chat_state import ChatState
from frontends.tui.screens.stream_handler import StreamHandler
from frontends.shared.commands import get_help_text
from memory.conversation_store import ConversationStore


class ChatScreen(Screen):
    """主聊天屏幕 — 薄壳，只做布局、事件路由、UI 渲染"""

    def __init__(self, agent, config, store: ConversationStore = None, model_manager=None, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent
        self.config = config
        self.store = store or ConversationStore()
        self.model_manager = model_manager
        # 状态管理层（全量历史、加载保存、命令）
        self.state = ChatState(self)
        # 流式处理层
        self.stream = StreamHandler(self, self.state)

    def compose(self):
        yield ChatPanel(id="chat-panel")
        yield InputBar(id="input-bar")

    def on_mount(self):
        self.state.try_load_latest()
        self.query_one(InputBar).focus_input()
        try:
            status = self.query_one("#status-bar")
            status.set_model_manager(self.model_manager)
            status.set_agent(self.agent)
        except Exception:
            pass

    def on_unmount(self):
        self.state.auto_save()

    # ── 事件处理 ──────────────────────────

    def on_text_area_changed(self, event):
        value = event.text_area.text
        input_bar = self.query_one(InputBar)
        if value.startswith("/") and not value.startswith("//"):
            input_bar.show_commands(value[1:])
        else:
            input_bar._hide_commands()

    def on_key(self, event):
        # ESC 中断生成
        if event.key == "escape" and self.state._generating:
            self.stream.cancel()
            self.query_one(InputBar).focus_input()
            event.stop()
            return

        try:
            cmd_list = self.query_one("#cmd-list")
        except Exception:
            cmd_list = None
        if cmd_list and event.key in ("down", "up"):
            cmd_list.focus()
            if event.key == "down":
                cmd_list.action_cursor_down()
            else:
                cmd_list.action_cursor_up()
            event.stop()

    def on_input_bar_command_selected(self, event: InputBar.CommandSelected):
        input_widget = self.query_one("#main-input")
        input_widget.load_text(event.command + " ")
        input_widget.focus()

    def on_input_bar_submitted(self, event: InputBar.Submitted):
        user_input = event.value
        panel = self.query_one(ChatPanel)

        if user_input.startswith("/"):
            if user_input.strip() == "/":
                self.state._show_command_list()
            else:
                self.state.handle_command(user_input)
            return

        panel.add_user_message(user_input)
        self.state._full_history.append({"role": "user", "content": user_input, "ts": time.strftime("%Y-%m-%d %H:%M:%S")})
        panel.scroll_end(animate=False)
        self.state._generating = True
        asyncio.create_task(self.stream.run(user_input))

    def on_input_bar_history_selected(self, event: InputBar.HistorySelected):
        conv = event.conversation
        conv_id = conv["id"]
        panel = self.query_one(ChatPanel)

        try:
            self.state.auto_save()
            self.state.load_conversation(conv_id)
            panel.add_system_message(f"已加载: {conv.get('title', conv_id)}")
        except Exception as e:
            panel.add_system_message(f"加载失败: {e}")

        self.query_one(InputBar).focus_input()

    def on_confirm_widget_confirmed(self, event: ConfirmWidget.Confirmed):
        self.stream.resolve_confirm(event)
