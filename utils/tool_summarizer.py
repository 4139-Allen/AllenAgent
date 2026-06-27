"""
工具结果摘要化 — 对复杂的长内容调用 LLM 提炼关键结论

与截断的关系：
  - 互斥：同一结果要么摘要要么截断，不会既摘要又截断
  - 摘要的内容已经足够短，不需要再截断
  - 摘要失败时降级到截断，不阻塞主流程

使用场景：
  - 测试报告：需要理解通过/失败/跳过的详细原因
  - API 大量数据：需要提炼关键字段和统计
  - 数据库查询结果：需要理解数据含义
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.llm_provider import LLMProvider

# 字符数低于此值不值得调一次 API
SUMMARY_MIN_CHARS = 1500

# 摘要提示词
_SUMMARIZE_PROMPT = """请用 2-3 句话提炼以下工具执行结果的核心结论。

要求：
- 只保留最关键的信息（最终结果、统计数字、关键数据、错误原因）
- 丢弃进度、重复内容、日志细节、中间状态
- 用中文回复
- 不超过 200 字

内容：
{content}"""

# ── 错误检测 ───────────────────────────────────────────────

_ERROR_KEYWORDS = [
    "error", "traceback", "exception",
    "失败", "拒绝", "错误", "异常",
    "ModuleNotFoundError", "ImportError", "SyntaxError",
]


def _has_error(content: str) -> bool:
    """检测内容是否包含错误（含错误的不摘要，原样保留）"""
    content_lower = content.lower()
    return any(kw in content_lower for kw in _ERROR_KEYWORDS)


# ── 判断是否需要摘要 ───────────────────────────────────────


def should_summarize(tool_name: str, content: str, action: str | None = None) -> bool:
    """判断是否需要对工具结果进行 LLM 摘要化

    决策规则：
      - 长度 < SUMMARY_MIN_CHARS（1500）→ 否（不值得调一次 API）
      - 含错误/异常 → 否（必须原样保留）
      - 搜索/知识库 → 否（已够紧凑）
      - 读文件 → 否（结构在头部，截断更好）
      - shell → 是（测试报告/数据分析结果需要提炼）
      - 其他长内容 → 是（兜底尝试摘要）

    Args:
        tool_name: 工具名称
        content: 工具返回的结果文本
        action: 操作类型

    Returns:
        True = 需要摘要，False = 走截断
    """
    if len(content) < SUMMARY_MIN_CHARS:
        return False

    if _has_error(content):
        return False

    # 已够紧凑的工具
    if tool_name in ("search_web", "search_knowledge_base", "update_memory"):
        return False

    # file_io 系列：截断优于摘要
    if tool_name == "file_io":
        return False

    # shell：摘要候选（测试报告、数据统计等）
    if tool_name == "shell":
        return True

    # code_search 等：结果已经是 grep/glob 的结构化格式
    if tool_name in ("code_search",):
        return False

    # 兜底：未知工具的长内容尝试摘要
    return True


# ── LLM 摘要调用 ────────────────────────────────────────────


def summarize_with_llm(content: str, llm_provider: LLMProvider | None) -> str | None:
    """调用 LLM 对工具结果进行摘要

    Args:
        content: 原始工具结果文本
        llm_provider: LLM 提供器（非流式调用）

    Returns:
        str: 摘要文本（成功时）
        None: 失败时降级，调用方应走截断
    """
    if llm_provider is None:
        return None

    messages = [
        {
            "role": "user",
            "content": _SUMMARIZE_PROMPT.format(content=content),
        }
    ]

    try:
        response = llm_provider.chat(
            messages=messages,
            temperature=0.1,
            timeout=30.0,
            max_tokens=500,  # 给更多 token 空间
        )
        if response.get("success"):
            summary = response["content"].strip()
            # 摘要不能为空，且不能超过安全上限（2000 字符）
            if summary:
                if len(summary) > 2000:
                    summary = summary[:2000] + "...（摘要过长已截断）"
                return summary
    except Exception:
        pass

    return None


# ── 统一入口 ────────────────────────────────────────────────


def maybe_summarize(
    tool_name: str,
    content: str,
    llm_provider: LLMProvider | None,
    action: str | None = None,
) -> str | None:
    """统一入口：判断 → 摘要 → 失败降级

    调用方使用示例：

        from utils.tool_summarizer import maybe_summarize
        summarized = maybe_summarize(func_name, result_content, agent.llm_provider, action=...)
        if summarized is not None:
            memory_content = summarized
        else:
            memory_content = result_content  # 降级，走截断

    Args:
        tool_name: 工具名称
        content: 工具结果文本
        llm_provider: LLM 提供器
        action: 操作类型

    Returns:
        str: 摘要文本（成功时）
        None: 不需要摘要或摘要失败（调用方应走截断）
    """
    if not should_summarize(tool_name, content, action):
        return None

    return summarize_with_llm(content, llm_provider)
