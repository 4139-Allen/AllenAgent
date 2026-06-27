"""
工具基类
所有工具都继承自 BaseTool
"""

from abc import ABC, abstractmethod

from schemas.tool import ToolResult


class BaseTool(ABC):
    """
    工具基类
    所有工具都需要继承此类并实现 execute 方法
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        pass

    def validate_params(self, params: dict) -> tuple[bool, str]:
        """
        校验参数是否符合 schema

        Args:
            params: LLM 传入的参数

        Returns:
            (is_valid, error_message)
        """
        schema = self._get_parameters()
        properties = schema.get("properties", {})

        # 校验 required 字段
        for field in schema.get("required", []):
            if field not in params or params[field] is None:
                return False, f"缺少必填参数: {field}"

        # 校验 enum 和类型
        for field, value in params.items():
            prop = properties.get(field)
            if not prop:
                continue

            # enum 校验
            enum_values = prop.get("enum")
            if enum_values is not None and value not in enum_values:
                allowed = ", ".join(str(v) for v in enum_values)
                return False, f"参数 '{field}' 取值 '{value}' 无效，允许值: {allowed}"

            # type 校验
            expected_type = prop.get("type")
            if expected_type == "string" and not isinstance(value, str):
                return False, f"参数 '{field}' 应为字符串"
            if expected_type == "array" and not isinstance(value, list):
                return False, f"参数 '{field}' 应为数组"

        return True, ""

    def get_schema(self) -> dict:
        """
        获取工具的 JSON Schema（用于 LLM Function Calling）
        子类可以覆盖此方法自定义参数
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameters(),
        }

    def _get_parameters(self) -> dict:
        """
        获取参数定义
        子类应覆盖此方法定义具体参数
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def __repr__(self):
        return f"<Tool: {self.name}>"
