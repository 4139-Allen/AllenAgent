from dataclasses import dataclass, field


@dataclass
class StreamEvent:
    """Agent 流式事件，用于 TUI 实时更新"""
    type: str  # thinking / tool_call / tool_result / token / reflection / confirm / done / error
    content: str = ""
    name: str = ""
    args: dict = field(default_factory=dict)
    result: object = None
    duration: int = 0
    step: int = 0
    total: int = 0  # 子任务总数（subtask_done 事件用）
    count: int = 1  # 批量操作时的数量（同一工具连续调用合并）
    tool_call_id: str = ""  # LLM 返回的原始工具调用 id
    ref_type: str = ""
    summary: str = ""
    # confirm 专用
    confirm_question: str = ""
    confirm_callback: object = None  # callable: (bool) -> None
    # tool_result 专用：success / error / rejected / skipped
    tool_status: str = ""
    # file_change 专用
    file_action: str = ""  # created / modified / deleted
    file_path: str = ""
