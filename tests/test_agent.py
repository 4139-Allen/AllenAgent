"""Agent 核心测试 — ReAct 循环、流式事件、工具调用"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from agents.allen_agent import AllenAgent
from memory.short_term import ConversationMemory
from tools.file_tool import FileTool
from tools.shell_tool import ShellTool


@pytest.fixture
def agent():
    """带 mock LLM 的 Agent 实例"""
    llm = Mock()
    llm.context_window = 128000
    # 默认的 chat 返回值（_plan 等方法需要）
    llm.chat.return_value = {"success": True, "content": "测试默认回复", "tool_calls": None, "usage": {"total_tokens": 10}}
    a = AllenAgent(
        name="test_agent",
        llm_provider=llm,
        memory=ConversationMemory(max_turns=10),
        reflect_engine=None,
    )
    a.tools = {
        "file_io": FileTool(),
        "shell": ShellTool(),
    }
    a.memory.set_system_prompt("你是一个测试助手")
    return a


class TestReActLoop:
    def test_direct_answer(self, agent):
        """LLM 直接返回答案（不调工具）"""
        agent.llm_provider.chat.return_value = {
            "success": True,
            "content": "直接回答",
            "tool_calls": None,
            "usage": {"total_tokens": 50},
        }
        result = agent.run("你好")
        assert result["answer"] == "直接回答"
        assert result["tools_used"] == []

    def test_single_tool_call(self, agent):
        """单次工具调用"""
        # _plan 先消耗一次 chat，然后 ReAct 循环走两步
        agent.llm_provider.chat.side_effect = [
            {"success": True, "content": "查天气", "tool_calls": None, "usage": {"total_tokens": 10}},  # _plan
            {"success": True, "content": None, "tool_calls": [{"id": "call_1", "function": "shell", "arguments": '{"command": "echo ok"}'}], "usage": {"total_tokens": 60}},  # step 1
            {"success": True, "content": "命令执行成功", "tool_calls": None, "usage": {"total_tokens": 70}},  # step 2
        ]
        result = agent.run("执行命令")
        assert "成功" in result["answer"]
        assert "shell" in result["tools_used"]

    def test_empty_query(self, agent):
        """空问题"""
        result = agent.run("")
        assert result["source"] == "empty"

    def test_max_steps_exceeded(self, agent):
        """超过最大步数"""
        agent.max_steps = 2
        agent.llm_provider.chat.side_effect = [
            {"success": True, "content": "测试", "tool_calls": None, "usage": {"total_tokens": 10}},  # _plan
            {"success": True, "content": None, "tool_calls": [{"id": "call_1", "function": "shell", "arguments": '{"command": "echo loop"}'}], "usage": {"total_tokens": 60}},  # step 1
            {"success": True, "content": None, "tool_calls": [{"id": "call_2", "function": "shell", "arguments": '{"command": "echo loop"}'}], "usage": {"total_tokens": 60}},  # step 2
            {"success": True, "content": "操作次数过多，已自动终止", "tool_calls": None, "usage": {"total_tokens": 70}},  # _force_answer
        ]
        result = agent.run("循环测试")
        assert result["answer"], "应有兜底回答"

    def test_tool_not_found(self, agent):
        """调用了不存在的工具"""
        agent.llm_provider.chat.return_value = {
            "success": True,
            "content": None,
            "tool_calls": [{"id": "call_1", "function": "nonexistent_tool", "arguments": "{}"}],
            "usage": {"total_tokens": 60},
        }
        # 第二步：LLM 看到错误后应返回文本
        agent.llm_provider.chat.side_effect = [
            {"success": True, "content": "测试", "tool_calls": None, "usage": {"total_tokens": 10}},  # _plan
            {"success": True, "content": None, "tool_calls": [{"id": "call_1", "function": "nonexistent_tool", "arguments": "{}"}], "usage": {"total_tokens": 60}},  # step 1
            {"success": True, "content": "该工具不存在", "tool_calls": None, "usage": {"total_tokens": 70}},  # step 2
        ]
        result = agent.run("测试")
        assert result["answer"]


class TestStreamEvents:
    def test_stream_direct_answer(self, agent):
        """流式直接回答"""
        agent.llm_provider.chat_stream.return_value = [
            {"type": "token", "content": "这是"},
            {"type": "token", "content": "测试回答"},
            {"type": "usage", "usage": {"total_tokens": 50}},
        ]
        events = list(agent.run_stream("你好"))
        texts = [e.content for e in events if e.type == "token"]
        assert "".join(texts) == "这是测试回答"
        assert any(e.type == "done" for e in events)

    def test_stream_with_thinking(self, agent):
        """流式带思考过程"""
        # thinking_token 需 >= 20 字符才触发 THINK_MIN_LEN
        agent.llm_provider.chat_stream.return_value = [
            {"type": "thinking_token", "content": "用户问好我需要回复一个友好的问候语给你请稍等一下"},
            {"type": "token", "content": "你好！有什么可以帮你的吗？"},
            {"type": "usage", "usage": {"total_tokens": 60}},
        ]
        events = list(agent.run_stream("你好"))
        thinking_tokens = [e.content for e in events if e.type == "thinking_token"]
        assert thinking_tokens, "应有思考内容"
        assert any(e.type == "done" for e in events)

    def test_stream_tool_call(self, agent):
        """流式工具调用"""
        # 只返回一次 tool_calls，后续步骤返回最终回答
        _call_count = [0]
        def _stream_gen(messages, **kwargs):
            _call_count[0] += 1
            if _call_count[0] == 1:
                yield {"type": "thinking_token", "content": "需要查一下天气信息用shell工具来完成"}
                yield {"type": "tool_calls", "tool_calls": [{"id": "call_1", "function": "shell", "arguments": '{"command": "echo sunny"}'}]}
                yield {"type": "usage", "usage": {"total_tokens": 60}}
            else:
                yield {"type": "token", "content": "天气晴朗，适合出行"}
                yield {"type": "usage", "usage": {"total_tokens": 70}}
        agent.llm_provider.chat_stream.side_effect = _stream_gen
        events = list(agent.run_stream("天气"))
        assert any(e.type == "tool_call" for e in events), "应有工具调用事件"
        assert any(e.type == "done" for e in events)

    def test_stream_cancel(self, agent):
        """流式取消"""
        agent.llm_provider.chat_stream.return_value = [
            {"type": "token", "content": "正在"},
            {"type": "token", "content": "回答"},
        ]
        # 设置取消信号
        agent._cancel_event.set()
        events = list(agent.run_stream("测试取消"))
        assert any(e.type == "cancelled" for e in events)

    def test_stream_error(self, agent):
        """流式错误"""
        agent.llm_provider.chat_stream.side_effect = RuntimeError("API 错误")
        events = list(agent.run_stream("测试错误"))
        assert any(e.type == "error" for e in events)
