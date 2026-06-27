"""
模型管理器
管理多个 LLMProvider，支持运行时切换
"""

import logging
from infrastructure.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class ModelManager:
    """
    模型管理器

    持有多个 LLMProvider 实例，按需创建和切换。
    同一个 model config 只创建一次 provider（缓存）。
    """

    def __init__(self, config):
        """
        Args:
            config: AppConfig 实例
        """
        self.config = config
        self._providers: dict[str, LLMProvider] = {}  # model_name → provider
        self._current_model: str = config.default_model

    @property
    def current_model(self) -> str:
        return self._current_model

    @property
    def current_provider(self) -> LLMProvider:
        return self.get_provider(self._current_model)

    def get_provider(self, model_name: str) -> LLMProvider:
        """获取指定模型的 provider（不存在则创建）"""
        if model_name not in self._providers:
            self._providers[model_name] = self._create_provider(model_name)
        return self._providers[model_name]

    def switch(self, model_name: str) -> str:
        """
        切换当前模型

        Args:
            model_name: 模型名称或 model ID

        Returns:
            切换结果描述
        """
        mc = self.config.get_model_config(model_name)
        if not mc:
            available = [f"{m.name} ({m.model})" for m in self.config.available_models]
            return f"  ❌ 未知模型: {model_name}\n  可用: {', '.join(available)}"

        # 检查 API key
        if not mc.api_key:
            return f"  ❌ {mc.name} 需要在 models.yaml 中配置 api_key"

        self._current_model = mc.model
        vision_tag = " [多模态]" if mc.has_vision else ""
        return f"  ✓ 已切换到 {mc.name} ({mc.model}){vision_tag}"

    def list_models(self) -> str:
        """列出所有可用模型"""
        lines = [f"  可用模型 (当前: {self._current_model}):"]
        for mc in self.config.available_models:
            status = "✓" if mc.api_key else "✗"
            current = "  <- 当前" if mc.model == self._current_model else ""
            vision = " [多模态]" if mc.has_vision else ""
            lines.append(f"    {status} {mc.name:<20} {mc.model:<24}{vision}{current}")
        return "\n".join(lines)

    def _create_provider(self, model_name: str) -> LLMProvider:
        """根据模型配置创建 LLMProvider"""
        mc = self.config.get_model_config(model_name)
        if not mc:
            raise ValueError(f"未知模型: {model_name}")

        if not mc.api_key:
            raise ValueError(f"缺少 API key，请在 models.yaml 中配置")

        return LLMProvider(
            api_key=mc.api_key,
            base_url=mc.base_url,
            model=mc.model,
            max_tokens=mc.max_tokens,
            context_window=mc.context_window,
            protocol=mc.protocol,
        )
