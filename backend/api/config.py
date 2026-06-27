"""API 配置"""

from dataclasses import dataclass, field


@dataclass
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False

    allow_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ])

    docs_enabled: bool = True

    @classmethod
    def from_env(cls):
        import os
        return cls(
            host=os.getenv("API_HOST", "127.0.0.1"),
            port=int(os.getenv("API_PORT", "8000")),
        )
