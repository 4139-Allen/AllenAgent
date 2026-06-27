#!/usr/bin/env python3
"""API 启动入口"""

import sys
import uvicorn
from api.config import ApiConfig


def main():
    cfg = ApiConfig.from_env()
    reload = "--reload" in sys.argv
    print(f"  → Allen Agents API: http://{cfg.host}:{cfg.port}")
    print(f"  → Swagger 文档:     http://{cfg.host}:{cfg.port}/docs")
    uvicorn.run("api.app:app", host=cfg.host, port=cfg.port, reload=reload)


if __name__ == "__main__":
    main()
