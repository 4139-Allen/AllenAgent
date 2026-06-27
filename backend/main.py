"""
Allen Agents API 入口

用法:
    python -m backend.main
    python -m backend.main --reload
    uvicorn backend.app:app --reload
"""

import sys
from pathlib import Path

# 将 backend/ 加入 sys.path（确保所有模块可导入）
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# 导入 FastAPI 应用（此时 backend/ 已在 sys.path，模块导入正常）
import uvicorn
from api.config import ApiConfig


def main():
    cfg = ApiConfig.from_env()
    reload = "--reload" in sys.argv

    print(f"  → Allen Agents API: http://{cfg.host}:{cfg.port}")
    print(f"  → Swagger 文档:     http://{cfg.host}:{cfg.port}/docs")
    print()

    uvicorn.run(
        "api.app:app",
        host=cfg.host,
        port=cfg.port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
