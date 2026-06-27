"""测试共享 fixtures"""

from unittest.mock import MagicMock, Mock
import pytest

from memory.short_term import ConversationMemory
from tools.file_tool import FileTool
from tools.shell_tool import ShellTool


@pytest.fixture
def memory():
    """基本的对话记忆实例"""
    m = ConversationMemory(max_turns=10)
    m.set_system_prompt("你是一个测试助手")
    return m


@pytest.fixture
def mock_llm():
    """Mock LLM provider"""
    llm = Mock()
    llm.chat.return_value = {
        "success": True,
        "content": "测试回答",
        "tool_calls": None,
        "usage": {"total_tokens": 100},
    }
    return llm


@pytest.fixture
def file_tool():
    return FileTool()


@pytest.fixture
def shell_tool():
    return ShellTool()
