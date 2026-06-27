"""
工具权限策略
- 工具分级（只读/写入/危险）
- 上下文感知的权限控制
- 操作确认机制
"""

from dataclasses import dataclass


@dataclass
class ToolPolicyResult:
    """策略检查结果"""
    allowed: bool
    reason: str
    needs_confirm: bool = False


class ToolPolicy:
    """
    工具权限策略管理器

    分级：
        READ    — 只读操作，随时可用
        WRITE   — 写入操作，默认允许
        DANGER  — 危险操作，默认需确认
    """

    TOOL_LEVELS = {
        "search_knowledge_base": "READ",
        "search_web":            "READ",
        "file_io":               "WRITE",
        "read_image":            "READ",
        "update_memory":         "WRITE",
        "shell":                 "DANGER",
    }

    # 系统/敏感路径 → 拒绝
    BLOCK_PATTERNS = [
        (r"^C:\\Windows", "file_io"),
        (r"^/etc", "file_io"),
        (r"^/usr", "file_io"),
        (r"^/System", "file_io"),
        (r"^/bin", "file_io"),
        (r"^/sbin", "file_io"),
        (r"\.env(\..*)?$", "file_io"),
        (r"\.ssh", "file_io"),
        (r"id_rsa", "file_io"),
        (r"id_ed25519", "file_io"),
    ]

    def __init__(self, require_confirm_for_write: bool = False):
        self.require_confirm_for_write = require_confirm_for_write

    def check(self, tool_name: str, kwargs: dict) -> ToolPolicyResult:
        """检查工具调用是否允许"""
        level = self.TOOL_LEVELS.get(tool_name, "READ")

        # file_io 动态判断
        if tool_name == "file_io":
            action = kwargs.get("action", "read")
            if action in ("read", "list"):
                return ToolPolicyResult(allowed=True, reason="")
            # 写入/删除：根据风险级别决定
            risk = self._check_file_risk(kwargs)
            if risk["level"] == "block":
                return ToolPolicyResult(allowed=False, reason=risk["reason"])
            if risk["level"] == "safe":
                return ToolPolicyResult(allowed=True, reason="")
            # 需要确认
            reason = risk["reason"] or f"{action}: {kwargs.get('filepath', '')}"
            return ToolPolicyResult(allowed=True, reason=reason, needs_confirm=True)

        # shell 动态判断
        if tool_name == "shell":
            risk = self._check_shell_risk(kwargs)
            if risk["level"] == "block":
                return ToolPolicyResult(allowed=False, reason=risk["reason"])
            # 所有 shell 命令都需要确认
            reason = risk["reason"] or kwargs.get("command", "")
            return ToolPolicyResult(allowed=True, reason=reason, needs_confirm=True)

        # READ — 放行
        if level == "READ":
            return ToolPolicyResult(allowed=True, reason="")

        # WRITE — 按配置
        if level == "WRITE":
            if self.require_confirm_for_write:
                return ToolPolicyResult(allowed=True, reason="", needs_confirm=True)
            return ToolPolicyResult(allowed=True, reason="")

        # DANGER — 需确认
        return ToolPolicyResult(allowed=True, reason="", needs_confirm=True)

    def _check_shell_risk(self, kwargs: dict) -> dict:
        """检查 shell 命令风险"""
        command = kwargs.get("command", "")
        if not command:
            return {"level": "block", "reason": "命令不能为空"}

        # 导入 ShellTool 的检查逻辑
        import re

        # 黑名单
        BLACKLIST = [
            r"rm\s+-rf\s+/", r"del\s+/[sS]\s+/[qQ]", r"format\s+[a-zA-Z]:",
            r"diskpart", r"regedit", r"reg\s+(delete|add)", r"shutdown",
            r"taskkill\s+/f", r"net\s+user", r"chmod\s+777", r"mkfs",
            r"dd\s+if=", r">\s*/dev/sd", r"Remove-Item.*-Recurse.*-Force.*C:\\",
        ]
        for pattern in BLACKLIST:
            if re.search(pattern, command, re.IGNORECASE):
                return {"level": "block", "reason": "危险命令，已拦截"}

        # 确认名单
        CONFIRM = [
            (r"pip\s+(install|uninstall)", "Python 包管理"),
            (r"npm\s+(install|uninstall)", "Node 包管理"),
            (r"yarn\s+add", "Node 包管理"),
            (r"git\s+(push|pull|checkout|reset|rebase|merge|branch\s+-[dD])", "Git 操作"),
            (r"docker\s+(rm|rmi|stop|kill)", "Docker 操作"),
            (r"(apt|brew|choco|winget)\s+(install|remove|uninstall)", "系统包管理"),
            (r"(Remove-Item|del\s+|rmdir|mv\s+|Move-Item)", "文件操作"),
            (r"cp\s+-[rR]|Copy-Item.*-Recurse", "复制目录"),
            (r"(curl|wget).*\|\s*(bash|sh|python)", "管道执行脚本"),
            (r"(Start-Process|Invoke-Expression|Invoke-WebRequest)", "PowerShell 操作"),
        ]
        for pattern, desc in CONFIRM:
            if re.search(pattern, command, re.IGNORECASE):
                return {"level": "confirm", "reason": f"{desc}: {command}"}

        return {"level": "safe", "reason": ""}

    def _check_file_risk(self, kwargs: dict) -> dict:
        """检查文件操作风险"""
        import re
        filepath = kwargs.get("filepath", "")

        # 检查拒绝模式
        for pattern, pattern_tool in self.BLOCK_PATTERNS:
            if pattern_tool == "file_io":
                if re.search(pattern, filepath, re.IGNORECASE):
                    return {"level": "block", "reason": f"拒绝访问敏感路径: {filepath}"}

        # 检查是否在项目目录外
        from pathlib import Path
        project_root = Path(__file__).parent.parent.resolve()
        target = Path(filepath).resolve()

        try:
            if target.is_relative_to(project_root):
                # Allen.md 免确认
                if target.name == "Allen.md" or "Allen.md" in str(target):
                    return {"level": "safe", "reason": ""}
                # 项目内：覆盖已有文件需确认
                if target.exists() and target.is_file():
                    return {"level": "confirm", "reason": f"覆盖已有文件: {filepath}"}
                return {"level": "safe", "reason": ""}
        except (ValueError, OSError):
            pass

        # 项目外 → 需确认
        return {"level": "confirm", "reason": f"写入项目目录外: {filepath}"}
