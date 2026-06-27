"""
集中配置管理
所有配置从 models.yaml 读取，一处管理
"""

from dataclasses import dataclass, field
from pathlib import Path

# 项目根目录（web_allen_agent/）
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class ModelConfig:
    """单个模型配置"""
    name: str                    # 显示名称
    provider: str                # 提供商 ID (deepseek / openai / zhipu / etc.)
    model: str                   # 模型 ID
    base_url: str                # API 地址
    api_key: str                 # API Key
    protocol: str = "openai"     # 协议类型 (openai / anthropic)
    has_vision: bool = False     # 是否支持图片
    max_tokens: int = 4096       # 默认最大输出
    context_window: int = 64000  # 上下文窗口大小（token）


@dataclass
class ProviderConfig:
    """提供商配置"""
    id: str                      # 提供商 ID
    name: str                    # 显示名称
    base_url: str                # API 地址
    api_key: str                 # API Key
    protocol: str = "openai"     # 协议类型
    models: dict = field(default_factory=dict)  # 模型列表 {model_id: model_info}


@dataclass
class AppConfig:
    """应用全局配置"""

    # 模型配置（从 models.yaml 加载）
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    default_provider: str = "deepseek"
    default_model: str = "deepseek-v4-flash"

    # 搜索引擎
    baidu_api_key: str = ""
    tavily_api_key: str = ""
    search_timeout: float = 120.0

    # RAG
    collection_name: str = "agent_knowledge"
    embedding_mode: str = "local"
    docs_folder: str = ""

    # Agent
    max_turns: int = 100
    max_steps: int = 5
    max_tokens: int = 4096
    max_reflections: int = 2       # 单次对话最大反思次数
    tracer_verbose: bool = True

    @property
    def available_models(self) -> list[ModelConfig]:
        """从 providers 动态生成可用模型列表"""
        models = []
        for provider_id, provider in self.providers.items():
            # 检查 API key 是否配置
            if not provider.api_key:
                continue

            for model_id, model_info in provider.models.items():
                models.append(ModelConfig(
                    name=model_info.get("name", model_id),
                    provider=provider_id,
                    model=model_id,
                    base_url=provider.base_url,
                    api_key=provider.api_key,
                    protocol=provider.protocol,
                    has_vision=model_info.get("has_vision", False),
                    max_tokens=model_info.get("max_tokens", 4096),
                    context_window=model_info.get("context_window", 64000),
                ))
        return models

    def get_model_config(self, model_name: str) -> ModelConfig | None:
        """按名称或 model ID 查找配置"""
        for mc in self.available_models:
            if model_name in (mc.name, mc.model):
                return mc
        return None

    def _load_models_config(self):
        """从 models.yaml 加载模型配置"""
        import yaml

        config_path = PROJECT_ROOT / "models.yaml"
        if not config_path.exists():
            print(f"警告: 未找到 {config_path}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return

        # 加载提供商配置
        for provider_id, provider_data in data.get("providers", {}).items():
            self.providers[provider_id] = ProviderConfig(
                id=provider_id,
                name=provider_data.get("name", provider_id),
                base_url=provider_data.get("base_url", ""),
                api_key=provider_data.get("api_key", ""),
                protocol=provider_data.get("protocol", "openai"),
                models=provider_data.get("models", {}),
            )

        # 加载默认配置
        self.default_provider = data.get("default_provider", "deepseek")
        self.default_model = data.get("default_model", "deepseek-v4-flash")

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从配置文件加载（保持向后兼容）"""
        from dotenv import load_dotenv
        import os

        load_dotenv()

        config = cls()
        config._load_models_config()

        # 搜索引擎（仍从 .env 读取）
        config.baidu_api_key = os.getenv("BAIDU_API_KEY", "")
        config.tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        config.search_timeout = float(os.getenv("SEARCH_TIMEOUT", "120.0"))

        # RAG
        config.collection_name = os.getenv("COLLECTION_NAME", "agent_knowledge")
        config.embedding_mode = os.getenv("EMBEDDING_MODE", "local")
        config.docs_folder = os.getenv("DOCS_FOLDER", str(PROJECT_ROOT / "Rag_local_docs"))

        # Agent
        config.max_turns = int(os.getenv("MAX_TURNS", "100"))
        config.max_steps = int(os.getenv("MAX_STEPS", "5"))
        config.max_tokens = int(os.getenv("MAX_TOKENS", "4096"))
        config.max_reflections = int(os.getenv("MAX_REFLECTIONS", "2"))
        config.tracer_verbose = os.getenv("TRACER_VERBOSE", "true").lower() == "true"

        return config
