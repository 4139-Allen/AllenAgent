"""
持久记忆工具
让 Agent 自主判断并写入 Allen.md
"""

from tools.base import BaseTool
from schemas.tool import ToolResult


class UpdateMemoryTool(BaseTool):
    """
    持久记忆工具
    Agent 在对话中发现值得记住的信息时，自主调用此工具写入 Allen.md
    """

    def __init__(self, allen_memory=None):
        super().__init__(
            name="update_memory",
            description="将重要信息写入持久记忆（Allen.md）。当用户表达偏好、习惯、决定、重要事实、待办事项时调用。"
        )
        self.allen_memory = allen_memory

    def set_memory(self, allen_memory):
        """延迟绑定"""
        self.allen_memory = allen_memory
        return self

    def execute(self, section: str, content: str, **kwargs) -> ToolResult:
        """
        写入持久记忆

        Args:
            section: 段落名（用户偏好 / 项目约定 / 重要事实 / 待办）
            content: 要记住的内容
        """
        if not self.allen_memory:
            return ToolResult(
                success=False,
                data=None,
                error="持久记忆未初始化",
                source="memory",
            )

        if not content or not content.strip():
            return ToolResult(
                success=False,
                data=None,
                error="内容不能为空",
                source="memory",
            )

        # 校验段落名
        valid_sections = ["用户偏好", "项目约定", "重要事实", "待办"]
        if section not in valid_sections:
            section = "重要事实"  # 默认段落

        result_msg = self.allen_memory.add(section, content.strip())

        return ToolResult(
            success=True,
            data={"section": section, "content": content.strip(), "message": result_msg},
            source="memory",
        )

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": ["用户偏好", "项目约定", "重要事实", "待办"],
                    "description": "记忆分类：用户偏好（喜好习惯）、项目约定（规范规则）、重要事实（关键信息）、待办（待完成事项）"
                },
                "content": {
                    "type": "string",
                    "description": "要记住的内容，简洁明确"
                },
            },
            "required": ["section", "content"],
        }
