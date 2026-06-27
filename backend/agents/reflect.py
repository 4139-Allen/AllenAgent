"""
自我评估引擎
在关键节点让 LLM 评估结果质量，发现问题就修正
"""

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """反思结果"""
    quality: str       # "good" / "needs_improvement" / "failed"
    issue: str         # 问题描述
    action: str        # "continue" / "retry" / "switch_strategy" / "answer_now"
    suggestion: str    # 具体建议


class ReflectEngine:
    """
    自我评估引擎

    两个触发点：
    1. 工具返回后 — 结果是否有用
    2. 最终答案前 — 答案是否完整准确
    """

    def __init__(self, llm_provider, max_reflections: int = 2):
        self.llm_provider = llm_provider
        self.max_reflections = max_reflections
        self._reflection_count: int = 0
        self._retry_count: dict[str, int] = {}  # tool_name → retry count

    def reflect_on_tool_result(
        self,
        query: str,
        tool_name: str,
        tool_args: dict,
        tool_result: str,
    ) -> ReflectionResult:
        """
        评估工具调用结果

        触发条件：工具返回空结果或失败
        """
        if self._reflection_count >= self.max_reflections:
            return ReflectionResult(
                quality="good",
                issue="",
                action="continue",
                suggestion="已达到反思次数上限，继续执行",
            )

        self._reflection_count += 1

        prompt = f"""你是一个智能助手的自我评估模块。评估刚才的工具调用结果。

用户问题：{query}
调用工具：{tool_name}
工具参数：{json.dumps(tool_args, ensure_ascii=False)}
工具返回：{tool_result[:500]}

评估标准：
1. 结果是否包含有用信息？
2. 工具选择是否正确？
3. 参数（如搜索关键词）是否合适？

严格按以下 JSON 格式回复，不要有其他内容：
{{"quality": "good/needs_improvement/failed", "issue": "问题描述", "action": "continue/retry/switch_strategy", "suggestion": "具体建议"}}"""

        return self._call_llm(prompt)

    def reflect_on_answer(
        self,
        query: str,
        answer: str,
        tools_used: list,
        tool_results_summary: str,
    ) -> ReflectionResult:
        """
        评估最终答案质量

        触发条件：准备输出最终答案时
        """
        if self._reflection_count >= self.max_reflections:
            return ReflectionResult(
                quality="good",
                issue="",
                action="answer_now",
                suggestion="已达到反思次数上限",
            )

        self._reflection_count += 1

        prompt = f"""你是一个智能助手的自我评估模块。评估回答质量。

用户问题：{query}
使用的工具：{tools_used}
关键信息摘要：{tool_results_summary[:500]}
生成的回答：{answer[:500]}

评估标准：
1. 回答是否完整回答了用户的问题？
2. 回答是否基于工具返回的证据，而不是凭空编造？
3. 回答是否简洁准确？

严格按以下 JSON 格式回复，不要有其他内容：
{{"quality": "good/needs_improvement/failed", "issue": "问题描述", "action": "answer_now/retry", "suggestion": "具体建议"}}"""

        return self._call_llm(prompt)

    def should_reflect_tool(self, tool_name: str, result_data) -> bool:
        """
        判断是否需要对工具结果进行反思

        触发条件：
        - 结果为空
        - 结果为失败
        - 同一工具已重试过但仍然失败
        """
        # 结果为空
        if result_data is None:
            return True

        # 结果是空列表
        if isinstance(result_data, list) and len(result_data) == 0:
            return True

        # 结果是空 dict
        if isinstance(result_data, dict) and not result_data:
            return True

        return False

    def can_retry(self, tool_name: str) -> bool:
        """检查是否还能重试"""
        return self._retry_count.get(tool_name, 0) < 1

    def record_retry(self, tool_name: str):
        """记录一次重试"""
        self._retry_count[tool_name] = self._retry_count.get(tool_name, 0) + 1

    def reset(self):
        """重置状态（新对话时调用）"""
        self._reflection_count = 0
        self._retry_count.clear()

    def _call_llm(self, prompt: str) -> ReflectionResult:
        """调用 LLM 进行评估"""
        try:
            result = self.llm_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200,
            )

            if not result["success"]:
                return self._default_result()

            content = result["content"].strip()

            # 提取 JSON
            if "{" in content:
                json_str = content[content.index("{"):content.rindex("}") + 1]
                data = json.loads(json_str)

                return ReflectionResult(
                    quality=data.get("quality", "good"),
                    issue=data.get("issue", ""),
                    action=data.get("action", "continue"),
                    suggestion=data.get("suggestion", ""),
                )

            return self._default_result()

        except Exception as e:
            logger.warning(f"[Reflect] 评估失败: {e}")
            return self._default_result()

    def _default_result(self) -> ReflectionResult:
        """默认结果（评估失败时的安全降级）"""
        return ReflectionResult(
            quality="good",
            issue="",
            action="continue",
            suggestion="评估失败，默认继续",
        )
