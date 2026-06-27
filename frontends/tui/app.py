from textual.app import App
from textual.theme import Theme
from frontends.tui.screens.chat import ChatScreen
from frontends.tui.widgets.thought_block import ThoughtBlock


class AllenApp(App):
    """Allen Agent TUI"""

    TITLE = "Allen Agent"
    CSS_PATH = "styles.css"

    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
        ("ctrl+n", "new_conversation", "新对话"),
        ("ctrl+o", "toggle_thought", "展开/折叠"),
    ]

    def __init__(self, agent, config, store=None, model_manager=None, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent
        self.config = config
        self.store = store
        self.model_manager = model_manager
        self._register_pure_themes()
        self.theme = "pure-black"

    def on_mount(self):
        self.push_screen(ChatScreen(self.agent, self.config, store=self.store, model_manager=self.model_manager))

    def action_new_conversation(self):
        try:
            screen = self.screen
            if hasattr(screen, '_handle_command'):
                screen._handle_command("/new")
        except Exception:
            pass

    def _register_pure_themes(self):
        """注册纯黑/纯白主题"""
        self.register_theme(Theme(
            name="pure-black",
            primary="#4A9EFF",
            secondary="#6A6A8A",
            warning="#FFA62B",
            error="#E06060",
            success="#5ABF7A",
            accent="#A97BFF",
            foreground="#E8E8E8",
            background="#000000",
            surface="#111111",
            panel="#1A1A1A",
            dark=True,
        ))
        self.register_theme(Theme(
            name="pure-white",
            primary="#2563EB",
            secondary="#6B7280",
            warning="#D97706",
            error="#DC2626",
            success="#16A34A",
            accent="#7C3AED",
            foreground="#1A1A1A",
            background="#FFFFFF",
            surface="#F5F5F5",
            panel="#EEEEEE",
            dark=False,
        ))

    def action_toggle_thought(self):
        try:
            screen = self.screen
            panel = screen.query_one("ChatPanel")
            for child in reversed(list(panel.children)):
                if isinstance(child, ThoughtBlock):
                    child.toggle()
                    break
        except Exception:
            pass
