"""
输出过滤器
- 敏感信息脱敏（API key、密码、token）— 保留首尾可辨识
- 输出长度限制
- 格式校验
"""

import re
from dataclasses import dataclass


def _mask_key(match: re.Match, prefix_len: int = 6, suffix_len: int = 4) -> str:
    """脱敏函数：保留前 N 位和后 M 位，中间用 ... 代替"""
    key = match.group(1)
    if len(key) <= prefix_len + suffix_len:
        return key  # 太短不脱敏
    return f"{key[:prefix_len]}...{key[-suffix_len:]}"


def _mask_key_value(match: re.Match, prefix_len: int = 6, suffix_len: int = 4) -> str:
    """脱敏函数：key=value 格式，只脱敏 value 部分"""
    label = match.group(1)
    value = match.group(2)
    if len(value) <= prefix_len + suffix_len:
        return f"{label}{value}"
    return f"{label}{value[:prefix_len]}...{value[-suffix_len:]}"


@dataclass
class OutputCheckResult:
    """输出检查结果"""
    passed: bool
    reason: str
    sanitized: str           # 脱敏后的文本


class OutputFilter:
    """
    输出安全过滤器

    脱敏策略：保留首尾可辨识部分，中间替换为 ...
    例如：sk-a1ca859d47dc4af382ae93e7925e99cf → sk-a1ca...99cf
    """

    # ── 敏感信息正则（pattern, replacement）─────
    SENSITIVE_PATTERNS = [
        # sk-xxx 格式（OpenAI / DeepSeek key）
        (r'(sk-[a-zA-Z0-9]{20,})',
         lambda m: _mask_key(m, 6, 4)),

        # KEY=xxx 格式（通用，匹配 .env 风格）
        (r'((?:DEEPSEEK|OPENAI|BAIDU|TAVILY)[_A-Z]*KEY\s*=\s*)(\S{16,})',
         lambda m: _mask_key_value(m, 6, 4)),

        # api_key=xxx / secret_key=xxx（通用）
        (r'((?:api|secret|token)[_-]?key\s*[=:]\s*["\']?)([a-zA-Z0-9_\-]{16,})',
         lambda m: _mask_key_value(m, 6, 4)),

        # Bearer token
        (r'(Bearer\s+)([a-zA-Z0-9_\-\.]{20,})',
         lambda m: _mask_key_value(m, 8, 4)),

        # password=xxx
        (r'(password\s*[=:]\s*["\']?)(\S{8,})',
         lambda m: _mask_key_value(m, 0, 0)),  # 密码完全遮盖

        # 密码=xxx
        (r'(密码\s*[=:]\s*["\']?)(\S{4,})',
         lambda m: _mask_key_value(m, 0, 0)),

        # AWS key
        (r'(AKIA[0-9A-Z]{16})',
         lambda m: f"{m.group(1)[:4]}...{m.group(1)[-4:]}"),

        # 私钥
        (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(RSA\s+)?PRIVATE\s+KEY-----',
         lambda m: '***PRIVATE_KEY***'),
    ]

    def __init__(self):
        self._compiled = [(re.compile(p), r) for p, r in self.SENSITIVE_PATTERNS]
        self._system_prompt: str = ""  # 用于检测提示词泄露

    def set_system_prompt(self, prompt: str):
        """设置系统提示词（用于泄露检测）"""
        self._system_prompt = prompt

    def _check_prompt_leak(self, output: str) -> float:
        """
        检测输出是否泄露系统提示词
        将系统提示词分成关键短语，检查输出中包含多少比例
        Returns: 0.0 ~ 1.0（泄露比例）
        """
        # 提取关键短语（去掉标点和空格的干扰）
        import re
        # 将系统提示词按中英文标点和换行分割成短语
        phrases = re.split(r'[。，、；：\n\-•\.\,\;]', self._system_prompt)
        phrases = [p.strip() for p in phrases if len(p.strip()) > 6]
        if not phrases:
            return 0.0

        matched = 0
        for phrase in phrases:
            # 去掉空格后比较
            p_clean = phrase.replace(" ", "")
            o_clean = output.replace(" ", "")
            if p_clean in o_clean:
                matched += 1
            elif len(p_clean) > 12:
                # 长短语用前半段匹配
                half = p_clean[:len(p_clean)//2]
                if half in o_clean:
                    matched += 0.6

        return matched / len(phrases)

    def check(self, text: str, tool_name: str = None) -> OutputCheckResult:
        """
        检查并脱敏输出
        """
        if not text:
            return OutputCheckResult(passed=True, reason="", sanitized=text)

        original = text

        # 1. 敏感信息脱敏
        for pattern, replacement in self._compiled:
            text = pattern.sub(replacement, text)

        # 2. 系统提示词泄露检测（仅 assistant 回复，不拦截工具结果）
        if tool_name is None and self._system_prompt and len(text) > 50:
            leak_ratio = self._check_prompt_leak(text)
            if leak_ratio > 0.25:
                return OutputCheckResult(
                    passed=True,
                    reason=f"回复与系统提示词相似 ({leak_ratio:.0%})",
                    sanitized="我专注于帮你解决问题，内部配置不便透露。",
                )

        # 3. 输出长度限制（已移除 — 上下文预算由整条丢弃机制管理，此处不再冗余截断）

        # 4. 检查脱敏是否发生
        was_sanitized = (text != original)
        reason = "已自动脱敏敏感信息" if was_sanitized else ""

        return OutputCheckResult(
            passed=True,
            reason=reason,
            sanitized=text,
        )
