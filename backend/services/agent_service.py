"""
Agent 服务层

编排 Agent 创建 → 流式运行 → 对话保存 的完整生命周期。
"""
import logging
from pathlib import Path

from schemas.stream import StreamEvent

logger = logging.getLogger(__name__)

# 文本文件扩展名 — 直接读取内容
TEXT_EXTENSIONS = {'.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json', '.xml', '.yaml', '.yml', '.csv', '.ini', '.cfg', '.conf', '.log', '.sh', '.bat', '.ps1', '.sql', '.r', '.java', '.cpp', '.h', '.c', '.go', '.rs', '.rb', '.php'}


def _process_file(file: dict) -> str | None:
    """处理单个文件，返回文件内容的文本描述"""
    filepath = Path(file["path"])
    name = file.get("name", filepath.name)
    mime = file.get("type", "")

    if not filepath.exists():
        return f"[文件: {name} (路径不存在)]"

    try:
        # 图片文件：返回路径（Agent 可用 read_image 工具读取）
        if mime.startswith("image/"):
            return f"[图片文件: {name}] 路径: {filepath.resolve()}\n（Agent 可用 read_image 工具查看图片内容）"

        # 文本文件：直接读取内容
        if filepath.suffix.lower() in TEXT_EXTENSIONS or "text" in mime:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            if len(content) > 50000:
                content = content[:50000] + "\n\n...(文件过长，已截断前50000字符)"
            return f"[文件: {name}]\n```\n{content}\n```"

        # PDF 等其他文件：返回路径（Agent 可用相应工具读取）
        return f"[文件: {name}] 路径: {filepath.resolve()}\n类型: {mime}"

    except Exception as e:
        return f"[文件: {name}] 读取失败: {e}"


def run_agent_session(app_state, message: str, session_id: str | None, reasoning_effort: str | None = None, files: list[dict] | None = None, user_id: str | None = None):
    """
    运行 Agent 并自动保存对话。

    Args:
        app_state: 全局 AppState
        message: 用户消息
        session_id: 对话 ID（续聊时传入）
        reasoning_effort: 推理强度（low/medium/high）
        files: 关联的文件列表，每项含 name/path/type

    Returns:
        (stream_generator, saved_id_container)
        - stream_generator: 产出 StreamEvent 的同步生成器
        - saved_id_container: [saved_id] 列表，流结束后读取
    """
    # ── 处理文件 ──
    file_texts: list[str] = []
    if files:
        for f in files:
            text = _process_file(f)
            if text:
                file_texts.append(text)
                logger.info("[AgentService] 已处理文件: %s", f.get("name", f.get("path")))

    # ── 构建带文件内容的用户消息 ──
    if file_texts:
        file_section = "\n\n".join(file_texts)
        augmented_message = f"{message}\n\n---\n用户上传的文件：\n{file_section}"
    else:
        augmented_message = message

    agent = app_state.create_agent(session_id, user_id=user_id)
    if reasoning_effort:
        agent.reasoning_effort = reasoning_effort
    saved_id = [session_id]

    def _stream():
        nonlocal saved_id
        for event in agent.run_stream(augmented_message):
            if event.type == "confirm":
                logger.info("[AgentService] 跳过确认: %s", event.confirm_question)
                if event.confirm_callback:
                    event.confirm_callback(False, False)
                continue
            yield event

        # 流结束 → 保存
        saved_id[0] = app_state.store.save(agent.memory, saved_id[0], user_id=user_id)
        logger.info("[AgentService] 对话已保存: %s", saved_id[0])

    return _stream(), saved_id
