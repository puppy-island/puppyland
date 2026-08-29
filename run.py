#!/usr/bin/env python3
"""从 .env 读取 PORT 后启动 uvicorn"""
import os
import sys

# 确保项目根目录在 sys.path 中（供 subprocess 使用）
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(override=True)

    import uvicorn

    port = int(os.getenv("PORT", 8001))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run("backend_app.main:app", host=host, port=port, reload=True)
