"""在不启动网络端口的情况下运行一次 FastAPI ASGI 冒烟请求。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from backend.app.core.database import initialize_database
from backend.app.main import create_app


async def main() -> None:
    db_path = Path("backend/tests/.test-data/smoke.db")
    initialize_database(db_path)
    app = create_app(db_path)
    transport = httpx.ASGITransport(app=app)
    print("before client", flush=True)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", trust_env=False) as client:
        print("before request", flush=True)
        response = await asyncio.wait_for(client.get("/api/health"), timeout=5)
        print("after request", flush=True)
    print(response.status_code, response.json())


if __name__ == "__main__":
    asyncio.run(main())
