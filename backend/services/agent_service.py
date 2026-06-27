"""
Agent 服务层

编排 Agent 创建 → 流式运行 → 对话保存 的完整生命周期。
"""
import logging

from schemas.stream import StreamEvent

logger = logging.getLogger(__name__)


def run_agent_session(app_state, message: str, session_id: str | None):
    """
    运行 Agent 并自动保存对话。

    Args:
        app_state: 全局 AppState
        message: 用户消息
        session_id: 对话 ID（续聊时传入）

    Returns:
        (stream_generator, saved_id_container)
        - stream_generator: 产出 StreamEvent 的同步生成器
        - saved_id_container: [saved_id] 列表，流结束后读取
    """
    agent = app_state.create_agent(session_id)
    saved_id = [session_id]

    def _stream():
        nonlocal saved_id
        for event in agent.run_stream(message):
            if event.type == "confirm":
                logger.info("[AgentService] 跳过确认: %s", event.confirm_question)
                if event.confirm_callback:
                    event.confirm_callback(False, False)
                continue
            yield event

        # 流结束 → 保存
        saved_id[0] = app_state.store.save(agent.memory, saved_id[0])
        logger.info("[AgentService] 对话已保存: %s", saved_id[0])

    return _stream(), saved_id
