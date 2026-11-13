"""[AI-MOD 2026-11-12] RSFuzz 测试管理平台后端入口。

启动（在 ex/app 下）：
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
或：
  python -m app.main
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import batches, meta, overview, runs, scenarios
from app.core.config import load_settings

app = FastAPI(
    title="无人机集群算法逻辑漏洞发现系统 API",
    description="RSFuzz 平台的批次 / 任务 / 回放数据查询接口",
    version="1.0.0",
)

# 开发期前端跑在 5173，直接放开跨域；生产由同源反向代理承载
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (overview, meta, scenarios, batches, runs):
    app.include_router(module.router)


@app.get("/api/health")
def health() -> dict:
    s = load_settings()
    return {"ok": True, "db": s.dsn(), "service": "rsfuzz-api"}


if __name__ == "__main__":
    s = load_settings()
    uvicorn.run("app.main:app", host=s.api_host, port=s.api_port, reload=True)
