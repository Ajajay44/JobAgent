"""
FastAPI application — JobUndo Agent API.

Responsibilities:
- Receive agent run requests from Django (authenticated with X-Internal-Token)
- Execute LangGraph workflow (Phase 3+)
- Stream progress via Server-Sent Events (Phase 10)
- Expose health endpoint for Docker

Security:
- CORS restricted to Django origin only
- Every non-health endpoint requires X-Internal-Token header
- FastAPI is NOT meant to be publicly accessible in production
"""
import time
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from db.database import check_db_connection

logger = logging.getLogger(__name__)


# ── Startup / shutdown ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JobUndo agent service starting up...")
    logger.info(f"  Ollama URL : {settings.ollama_base_url}")
    logger.info(f"  LLM model  : {settings.llm_model} (configured, not loaded yet)")
    logger.info(f"  Embed model: {settings.embed_model}")
    yield
    logger.info("JobUndo agent service shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="JobUndo Agent API",
    description="Internal AI agent API. Not for public access.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Restrict to Django's origin only.
# Even in dev, FastAPI should not accept requests from arbitrary origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://django:8000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Internal authentication ───────────────────────────────────────────────────
def verify_internal_token(request: Request) -> None:
    """
    Dependency: verify that the request comes from our Django backend.

    Django sends the shared secret in the X-Internal-Token header.
    If it's missing or wrong, reject with 401.

    This is not user authentication — it's service-to-service authentication.
    In production, mutual TLS would be even stronger, but this is sufficient
    for a private Docker network where services are already isolated.
    """
    token = request.headers.get("X-Internal-Token", "")
    if not token or token != settings.internal_api_secret:
        logger.warning(
            f"Rejected request from {request.client.host} — bad internal token"
        )
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    """
    Public health endpoint. Docker healthcheck calls this.
    No auth required.
    """
    db_ok = await check_db_connection()
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if db_ok else "degraded",
            "service": "jobundo-agent",
            "timestamp": time.time(),
            "checks": {
                "database": "ok" if db_ok else "unreachable",
            },
        },
    )


# ── Agent endpoints ───────────────────────────────────────────────────────────
@app.post(
    "/api/agent/run",
    dependencies=[Depends(verify_internal_token)],
    tags=["Agent"],
)
async def start_agent_run(request: Request):
    """
    Start an agent run.

    Phase 1: Returns 501 — LangGraph execution not yet wired.
    Phase 3+: Will deserialize the request body, build AgentState,
              invoke agent_graph, and stream SSE events back to Django.
    """
    run_id = str(uuid.uuid4())
    logger.info(f"Agent run requested — run_id={run_id} (Phase 1: not implemented)")
    return JSONResponse(
        status_code=501,
        content={
            "run_id": run_id,
            "status": "not_implemented",
            "message": "Agent execution will be implemented in Phase 3.",
        },
    )


@app.get(
    "/api/agent/run/{run_id}/status",
    dependencies=[Depends(verify_internal_token)],
    tags=["Agent"],
)
async def get_run_status(run_id: str):
    """
    Get the current status of an agent run.

    Phase 1: Returns 501.
    Phase 3+: Will query the database for the AgentRun record.
    """
    return JSONResponse(
        status_code=501,
        content={
            "run_id": run_id,
            "status": "not_implemented",
            "message": "Run status will be implemented in Phase 3.",
        },
    )
