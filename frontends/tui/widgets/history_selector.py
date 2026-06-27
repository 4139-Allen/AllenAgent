from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.message import Message


class HistorySelector(OptionList):
    """可交互的历史对话选择器（上下键选择，回车确认）"""

    class Selected(Message):
        def __init__(self, conversation: dict):
            super().__init__()
            self.conversation = conversation

    def __init__(self, conversations: list[dict], **kwargs):
        self.conversations = conversations
        options = []
        for i, conv in enumerate(conversations):
            title = conv.get("title", "未命名")
            turns = conv.get("turn_count", 0)
            created = conv.get("created_at", "")
            options.append(Option(f"  {title}  ({turns}轮)  {created}", id=str(i)))
        super().__init__(*options, **kwargs)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        idx = int(event.option_id)
        if 0 <= idx < len(self.conversations):
            self.post_message(self.Selected(self.conversations[idx]))

    def on_key(self, event):
        if event.key == "escape":
            self.remove()
