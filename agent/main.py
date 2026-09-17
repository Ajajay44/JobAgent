"""
FastAPI application — JobUndo Agent API.

Phase 3: /api/agent/run is now fully implemented.
  - Receives AgentRunRequest from Django
  - Builds AgentState
  - Invokes LangGraph in a thread pool (non-blocking)
  - Returns AgentRunResponse with all parsed data

Security:
  - CORS restricted to Django origin only
  - X-Internal-Token required on every non-health endpoint
  - FastAPI is on an internal Docker network — not publicly exposed

Phase 10 will add SSE streaming to replace the synchronous call.
"""
import base64
import time
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from db.database import check_db_connection
from schemas_request import AgentRunRequest, AgentRunResponse
from state import AgentState
from graph import agent_graph

logger = logging.getLogger(__name__)


# ── Startup / shutdown ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("JobUndo agent service starting up...")
    logger.info(f"  Ollama URL : {settings.ollama_base_url}")
    logger.info(f"  LLM model  : {settings.llm_model}")
    logger.info(f"  Embed model: {settings.embed_model}")
    yield
    logger.info("JobUndo agent service shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="JobUndo Agent API",
    description="Internal AI agent API. Not for public access.",
    version="0.2.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://django:8000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Internal auth ─────────────────────────────────────────────────────────────
def verify_internal_token(request: Request) -> None:
    """
    Service-to-service authentication guard.
    Every non-health endpoint requires X-Internal-Token matching the shared secret.
    """
    token = request.headers.get("X-Internal-Token", "")
    if not token or token != settings.internal_api_secret:
        logger.warning(f"Rejected request — bad internal token from {request.client.host}")
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    """
    Public health endpoint for Docker healthcheck.
    Returns 200 (healthy) or 503 (degraded — DB unreachable).
    """
    db_ok = await check_db_connection()
    code = 200 if db_ok else 503
    return JSONResponse(
        status_code=code,
        content={
            "status": "healthy" if db_ok else "degraded",
            "service": "jobundo-agent",
            "timestamp": time.time(),
            "checks": {"database": "ok" if db_ok else "unreachable"},
        },
    )


# ── Agent run ─────────────────────────────────────────────────────────────────
@app.post(
    "/api/agent/run",
    response_model=AgentRunResponse,
    dependencies=[Depends(verify_internal_token)],
    tags=["Agent"],
)
async def start_agent_run(body: AgentRunRequest) -> AgentRunResponse:
    """
    Execute the full LangGraph agent pipeline.

    Flow:
      1. Validate request (Pydantic)
      2. Decode base64 PDF bytes
      3. Build AgentState
      4. Run agent_graph in thread pool (non-blocking for event loop)
      5. Return AgentRunResponse

    Why thread pool?
      LangGraph's graph.invoke() is synchronous. Running it directly in an
      async endpoint would block FastAPI's event loop for the entire LLM
      inference time (potentially minutes). asyncio.to_thread() offloads it
      to a worker thread while the event loop stays free to handle health
      checks and other requests.

    Timeout: no explicit timeout here — callers set their own httpx timeout.
    Phase 10 will replace this with SSE streaming.
    """
    run_id = body.run_id
    start_time = time.time()
    logger.info(
        f"[{run_id}] Agent run starting — "
        f"user={body.user_id} application={body.application_id}"
    )

    # ── Decode PDF bytes ──────────────────────────────────────────────────
    try:
        pdf_bytes = base64.b64decode(body.resume_pdf_base64)
    except Exception as e:
        logger.error(f"[{run_id}] Invalid base64 PDF: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid resume PDF encoding: {e}")

    # ── Build initial AgentState ──────────────────────────────────────────
    initial_state: AgentState = {
        "run_id": run_id,
        "user_id": body.user_id,
        "jd_raw": body.jd_raw,
        "jd_url": body.jd_url,
        "resume_pdf_bytes": pdf_bytes,
        "user_tone": body.user_tone,
        # Intermediate data — populated by nodes
        "jd_parsed": None,
        "resume_parsed": None,
        "skill_alignment": None,
        "company_intelligence": None,
        "resume_rewritten": None,
        "cover_letter_content": None,
        "cold_email_variants": None,
        "linkedin_referral": None,
        # Quality loop
        "quality_score": None,
        "quality_feedback": None,
        "retry_count": 0,
        "retry_target_node": None,
        # Final artifacts
        "resume_pdf": None,
        "cover_letter_pdf": None,
        # Observability — Annotated[List, operator.add] fields start as []
        "current_step": "starting",
        "steps_completed": [],
        "errors": [],
    }

    # ── Run LangGraph in a thread pool ────────────────────────────────────
    try:
        final_state: AgentState = await asyncio.to_thread(
            agent_graph.invoke, initial_state
        )
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[{run_id}] Graph execution failed: {type(e).__name__}: {e}")
        return AgentRunResponse(
            run_id=run_id,
            application_id=body.application_id,
            status="failed",
            errors=[f"Agent graph error: {str(e)}"],
            duration_ms=duration_ms,
        )

    # ── Build response ────────────────────────────────────────────────────
    duration_ms = int((time.time() - start_time) * 1000)
    errors = final_state.get("errors", [])

    # Determine status:
    #   completed  — parsing succeeded (at minimum)
    #   partial    — some nodes succeeded, some failed
    #   failed     — nothing useful was produced
    jd_ok = final_state.get("jd_parsed") is not None
    resume_ok = final_state.get("resume_parsed") is not None

    if jd_ok and resume_ok:
        run_status = "completed"
    elif jd_ok or resume_ok:
        run_status = "partial"
    else:
        run_status = "failed"

    logger.info(
        f"[{run_id}] Agent run finished — "
        f"status={run_status} duration={duration_ms}ms "
        f"steps={final_state.get('steps_completed', [])}"
    )

    return AgentRunResponse(
        run_id=run_id,
        application_id=body.application_id,
        status=run_status,
        jd_parsed=final_state.get("jd_parsed"),
        resume_parsed=final_state.get("resume_parsed"),
        skill_alignment=final_state.get("skill_alignment"),
        company_intelligence=final_state.get("company_intelligence"),
        resume_rewritten=final_state.get("resume_rewritten"),
        cover_letter_content=final_state.get("cover_letter_content"),
        cold_email_variants=final_state.get("cold_email_variants"),
        linkedin_referral=final_state.get("linkedin_referral"),
        steps_completed=final_state.get("steps_completed", []),
        errors=errors,
        duration_ms=duration_ms,
    )


# ── Run status ────────────────────────────────────────────────────────────────
@app.get(
    "/api/agent/run/{run_id}/status",
    dependencies=[Depends(verify_internal_token)],
    tags=["Agent"],
)
async def get_run_status(run_id: str):
    """
    Query the status of an agent run.

    Phase 3: Returns 501 — status tracking via DB is Phase 4+.
    Phase 4+: Will query AgentRun from PostgreSQL.

    For now, Django tracks status on its own Application model
    after receiving the AgentRunResponse from /api/agent/run.
    """
    return JSONResponse(
        status_code=501,
        content={
            "run_id": run_id,
            "detail": "Live run status polling not yet implemented (Phase 4+). "
                      "Query Django's /api/applications/{id}/run/ instead.",
        },
    )

