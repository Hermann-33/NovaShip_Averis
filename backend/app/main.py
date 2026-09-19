"""
NovaShip Averis API - FastAPI entrypoint.

    uvicorn app.main:app --reload --port 8000
    open http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

# Direct local runs start in backend/, while the shared environment file lives
# at the repository root. Existing process/container variables keep precedence.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.agent_routes import router as agent_router
from app.api.routes import router
from app.config import get_repo

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format='{"t":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("novaship")

app = FastAPI(
    title="NovaShip Averis - AI Shipping Inbox & SI<->BL Verification",
    version="1.0.0",
    description="Ingest -> secure -> classify -> extract -> deterministic seven-field compare -> evidence -> draft -> human approval -> notify -> audit.",
)

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins or ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.time()
    resp = await call_next(request)
    resp.headers["X-Process-Time-Ms"] = str(int((time.time() - t0) * 1000))
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal error", "category": "DATABASE_ERROR", "step": request.url.path, "recovery": "Retry; if it persists check backend logs.", "retryable": True})


@app.on_event("startup")
def startup() -> None:
    repo = get_repo()
    log.info("repository=%s cases=%d llm=%s", type(repo).__name__, len(repo.list_cases()), os.environ.get("LLM_PROVIDER", "none"))


app.include_router(router)
app.include_router(agent_router)
