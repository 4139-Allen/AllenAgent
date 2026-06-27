"""
安全护栏统一入口
串联所有检查，提供单一接口
"""

import logging
from dataclasses import dataclass

from guardrails.output_filter import OutputFilter, OutputCheckResult
from guardrails.tool_policy import ToolPolicy, ToolPolicyResult

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """护栏检查统一结果"""
    passed: bool
    stage: str           # "input" / "tool_policy" / "rate_limit" / "output"
    risk_level: str      # "safe" / "suspicious" / "blocked"
    reason: str
    sanitized_text: str  # 清洗后的文本（输入或输出）
    needs_confirm: bool = False  # 是否需要用户确认


class Guardrail:
    """
    安全护栏统一入口

    使用方式：
        guardrail = Guardrail(llm_provider=provider)

        # 输入检查
        result = guardrail.check_input(user_text)
        if not result.passed:
            return "输入不安全"

        # 工具调用检查
        result = guardrail.check_tool("file_io", {"action": "write", "filepath": "..."})
        if not result.passed:
            return "操作被拒绝"

        # 输出检查
        result = guardrail.check_output(agent_reply)
        print(result.sanitized_text)  # 脱敏后的文本
    """

    def __init__(
        self,
        llm_provider=None,
        enable_llm_check: bool = False,
        require_confirm_for_write: bool = False,
    ):
        self.output_filter = OutputFilter()
        self.tool_policy = ToolPolicy(require_confirm_for_write=require_confirm_for_write)

    def set_system_prompt(self, prompt: str):
        """设置系统提示词（用于泄露检测）"""
        self.output_filter.set_system_prompt(prompt)

    def check_input(self, text: str) -> GuardrailResult:
        """检查用户输入（已禁用规则检测，仅透传）"""
        return GuardrailResult(
            passed=True,
            stage="input",
            risk_level="safe",
            reason="",
            sanitized_text=text,
        )

    def check_tool(self, tool_name: str, kwargs: dict) -> GuardrailResult:
        """检查工具调用（策略）"""
        # 策略检查
        policy_result = self.tool_policy.check(tool_name, kwargs)
        if not policy_result.allowed:
            logger.warning(f"[Guardrail] 策略拒绝: {policy_result.reason}")
            return GuardrailResult(
                passed=False,
                stage="tool_policy",
                risk_level="blocked",
                reason=policy_result.reason,
                sanitized_text="",
            )

        return GuardrailResult(
            passed=True,
            stage="tool_policy",
            risk_level="safe",
            reason=policy_result.reason,
            sanitized_text="",
            needs_confirm=policy_result.needs_confirm,
        )

    def check_output(self, text: str, tool_name: str = None) -> GuardrailResult:
        """检查 Agent 输出"""
        result = self.output_filter.check(text, tool_name)

        if result.reason:
            logger.info(f"[Guardrail] 输出处理: {result.reason}")

        return GuardrailResult(
            passed=result.passed,
            stage="output",
            risk_level="safe",
            reason=result.reason,
            sanitized_text=result.sanitized,
        )

    def get_stats(self) -> dict:
        """获取护栏统计"""
        return {}
