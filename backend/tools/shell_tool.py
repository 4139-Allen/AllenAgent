"""
Shell 执行工具
Agent 可通过此工具执行终端命令
支持 Windows (PowerShell) 和 Linux/Mac (bash)
"""

import os
import re
import subprocess
import platform
import shlex
from tools.base import BaseTool
from schemas.tool import ToolResult

# ── 黑名单（直接拒绝）──────────────────────────
BLACKLIST_PATTERNS = [
    r"rm\s+-rf\s+/",           # rm -rf /
    r"del\s+/[sS]\s+/[qQ]",    # del /s /q
    r"format\s+[a-zA-Z]:",     # format C:
    r"diskpart",               # diskpart
    r"regedit",                # regedit
    r"reg\s+(delete|add)",     # reg delete/add
    r"shutdown",               # shutdown
    r"taskkill\s+/f",          # taskkill /f
    r"net\s+user",             # net user (创建/删除用户)
    r"chmod\s+777",            # chmod 777
    r"mkfs",                   # mkfs (格式化)
    r"dd\s+if=",               # dd (磁盘写入)
    r">\s*/dev/sd",            # 写入磁盘设备
    r"Remove-Item.*-Recurse.*-Force.*C:\\",  # PowerShell rm -rf C:\
]

# ── 确认名单（需用户确认）────────────────────────
CONFIRM_PATTERNS = [
    (r"pip\s+install", "安装 Python 包"),
    (r"pip\s+uninstall", "卸载 Python 包"),
    (r"npm\s+install", "安装 Node 包"),
    (r"npm\s+uninstall", "卸载 Node 包"),
    (r"yarn\s+add", "安装 Node 包"),
    (r"git\s+(push|pull|checkout|reset|rebase|merge)", "Git 操作"),
    (r"git\s+branch\s+-[dD]", "删除 Git 分支"),
    (r"docker\s+(rm|rmi|stop|kill)", "Docker 操作"),
    (r"apt\s+(install|remove)", "系统包管理"),
    (r"brew\s+(install|uninstall)", "系统包管理"),
    (r"choco\s+(install|uninstall)", "系统包管理"),
    (r"winget\s+(install|uninstall)", "系统包管理"),
    (r"Remove-Item", "PowerShell 删除"),
    (r"del\s+", "删除文件"),
    (r"rmdir", "删除目录"),
    (r"mv\s+", "移动/重命名文件"),
    (r"Move-Item", "PowerShell 移动"),
    (r"cp\s+-[rR]", "复制目录"),
    (r"Copy-Item.*-Recurse", "PowerShell 复制目录"),
    (r"curl.*\|\s*(bash|sh|python)", "管道执行脚本"),
    (r"wget.*\|\s*(bash|sh|python)", "管道执行脚本"),
    (r"Start-Process", "启动进程"),
    (r"Invoke-Expression", "执行表达式"),
    (r"Invoke-WebRequest", "Web 请求"),
]

# ── 超时（秒）──────────────────────────────────
TIMEOUT = 30


class ShellTool(BaseTool):
    """
    Shell 执行工具
    执行终端命令，返回 stdout/stderr/exit_code
    """

    def __init__(self):
        super().__init__(
            name="shell",
            description="执行终端命令（PowerShell/bash）。适用于：列出目录内容、运行脚本、安装包、查询系统信息、Git操作等。列目录可用 ls 或 Get-ChildItem，比 file_io 的 list 输出更丰富（大小、时间等）。"
        )
        self.is_windows = platform.system() == "Windows"

    def execute(self, command: str, **kwargs) -> ToolResult:
        # 黑名单检查
        for pattern in BLACKLIST_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return ToolResult(
                    success=False, data=None,
                    error=f"命令被安全策略拒绝：匹配黑名单规则",
                    source="shell",
                )

        # 选择 shell
        if self.is_windows:
            # 设 stdout 编码为 UTF-8 + 文件读写默认 UTF-8，解决中文系统和 PowerShell 5.1 编码问题
            shell_cmd = ["powershell", "-NoProfile", "-Command",
                         "$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                         "$PSDefaultParameterValues['*:Encoding']='utf8'; " + command]
        else:
            shell_cmd = ["bash", "-c", command]

        try:
            result = subprocess.run(
                shell_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=TIMEOUT,
                cwd=os.getcwd(),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            stdout = result.stdout.strip() if result.stdout else ""
            stderr = result.stderr.strip() if result.stderr else ""
            exit_code = result.returncode

            # 截断过长输出
            max_len = 2000
            if len(stdout) > max_len:
                stdout = stdout[:max_len] + f"\n... (截断，共 {len(result.stdout)} 字符)"
            if len(stderr) > max_len:
                stderr = stderr[:max_len] + f"\n... (截断，共 {len(result.stderr)} 字符)"

            success = exit_code == 0
            data = {
                "command": command,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
            }

            if success:
                return ToolResult(success=True, data=data, source="shell")
            else:
                return ToolResult(
                    success=False, data=data,
                    error=f"命令退出码 {exit_code}: {stderr[:200]}",
                    source="shell",
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, data=None,
                error=f"命令超时（{TIMEOUT}秒）: {command}",
                source="shell",
            )
        except FileNotFoundError:
            return ToolResult(
                success=False, data=None,
                error=f"找不到 shell: {'PowerShell' if self.is_windows else 'bash'}",
                source="shell",
            )
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e), source="shell")


    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的终端命令（Windows 用 PowerShell 语法，Linux/Mac 用 bash 语法）"
                },
            },
            "required": ["command"],
        }
