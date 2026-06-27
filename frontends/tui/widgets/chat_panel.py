from textual.widgets import Static
from textual.containers import ScrollableContainer
from frontends.tui.widgets.messages import UserMessage, AssistantMessage
from frontends.tui.widgets.thought_block import ThoughtBlock
from frontends.tui.widgets.compressing_widget import CompressingWidget


class ChatPanel(ScrollableContainer):
    """聊天消息滚动区"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.follow = True  # 自动跟随底部（用户手动滚动上去后停止跟随）
        self._current_assistant: AssistantMessage | None = None
        self._current_thought: ThoughtBlock | None = None
        self._last_thought: ThoughtBlock | None = None  # 已被 finalize 的推理块，用于后续更新耗时
        self._current_compressing: CompressingWidget | None = None

    def add_user_message(self, content):
        """添加用户消息"""
        self._finalize_current()
        widget = UserMessage(str(content) if content else "")
        self.mount(widget)

    def start_assistant_message(self) -> AssistantMessage:
        """开始一条 Agent 回复（流式），保留推理块不终稿"""
        if self._current_assistant:
            self._current_assistant.finalize()
            self._current_assistant = None
        if self._current_compressing:
            self._current_compressing.remove()
            self._current_compressing = None
        widget = AssistantMessage()
        self.mount(widget)
        self._current_assistant = widget
        return widget

    def _auto_scroll(self):
        if self.scroll_y is not None and self.max_scroll_y is not None:
            if self.scroll_y >= self.max_scroll_y - 1:
                self.scroll_end(animate=False)

    def append_token(self, token):
        if self._current_assistant and token:
            self._current_assistant.append_token(str(token))
        self._auto_scroll()

    def finalize_assistant_message(self, elapsed: int | None = None):
        """结束当前 Agent 回复"""
        if self._current_assistant:
            self._current_assistant.finalize(elapsed=elapsed)
            self._current_assistant = None

    def start_thought_block(self) -> ThoughtBlock:
        """开始新的推理过程块（生成中使用）"""
        self._finalize_thought()
        widget = ThoughtBlock()
        self.mount(widget)
        self._current_thought = widget
        return widget

    def get_or_create_thought_block(self) -> ThoughtBlock:
        """获取或创建推理块（流式追加时用）"""
        if self._current_thought is None:
            self._finalize_thought()
            widget = ThoughtBlock()
            self.mount(widget)
            self._current_thought = widget
        return self._current_thought

    def append_thought_thinking(self, token: str):
        block = self.get_or_create_thought_block()
        block.append_thinking(token)
        self._auto_scroll()

    def add_thought_tool_line(self, text: str):
        block = self.get_or_create_thought_block()
        block.add_tool_call_line(text)
        self._auto_scroll()

    def finalize_tool_call(self):
        if self._current_thought:
            self._current_thought.finalize_tool_call()

    def add_thought_tool_result_line(self, text: str):
        block = self.get_or_create_thought_block()
        block.add_tool_result_line(text)
        self._auto_scroll()

    def finish_thought_block(self, elapsed: int | None = None):
        """结束推理过程块并设置最终耗时"""
        if self._current_thought:
            self._current_thought.finish(elapsed)
            self._current_thought = None
        elif self._last_thought and elapsed is not None:
            # 已被 _finalize_thought 提前结束的，更新耗时
            self._last_thought.set_elapsed(elapsed)

    def _finalize_thought(self):
        """强制结束当前推理块"""
        if self._current_thought:
            # 空推理块（只有计时没有内容）直接移除，不留在面板上
            if not self._current_thought._segments:
                self._current_thought.remove()
            else:
                self._current_thought.finish()
                self._last_thought = self._current_thought
            self._current_thought = None

    def mount_thought_block(self, block: ThoughtBlock):
        """挂载一个已完成的推理块（用于历史回放）"""
        self._finalize_current()
        self.mount(block)

    def start_compressing(self) -> CompressingWidget:
        """开始压缩进度动画"""
        self._finalize_current()
        widget = CompressingWidget()
        self.mount(widget)
        self._current_compressing = widget
        return widget

    def finish_compressing(self):
        """结束压缩进度动画"""
        if self._current_compressing:
            self._current_compressing.remove()
            self._current_compressing = None

    def _scroll_follow(self):
        """如果用户在底部，自动跟随滚动"""
        try:
            if self.scroll_y is not None and self.max_scroll_y is not None:
                if self.scroll_y >= self.max_scroll_y - 1:
                    self.scroll_end(animate=False)
        except Exception:
            pass

    def add_system_message(self, content):
        """添加系统消息到面板"""
        block = ThoughtBlock()
        block.append_thinking(f"⚠️ {content}")
        block.finish()
        self.mount(block)

    def add_artifact(self, widget):
        """添加制品（代码块/文件内容）到面板，先结束当前流式状态"""
        self._finalize_current()
        self.mount(widget)
        self._auto_scroll()

    def clear_all(self):
        """清空所有消息"""
        self._finalize_current()
        for child in list(self.children):
            child.remove()
        self._current_assistant = None
        self._current_thought = None
        self._last_thought = None
        self._current_compressing = None

    def _finalize_current(self):
        """结束当前流式状态"""
        if self._current_assistant:
            self._current_assistant.finalize()
            self._current_assistant = None
        if self._current_compressing:
            self._current_compressing.remove()
            self._current_compressing = None
        self._finalize_thought()
