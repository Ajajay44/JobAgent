"""
AgentService — Django-side HTTP client for calling the FastAPI agent.

Responsibilities:
- Read the resume PDF from file storage and base64-encode it
- POST the job application data to FastAPI's /api/agent/run
- Return the agent result dict back to the view

Design:
- Synchronous (uses httpx.Client, not AsyncClient) because Django views are sync
- All configuration comes from Django settings (FASTAPI_URL, INTERNAL_API_SECRET)
- Timeout is generous (5 min) to accommodate slow local LLM inference
- Returns a plain dict — the view decides what to do with it

Phase 10 will replace this with an async SSE stream.
"""
import base64
import logging
import uuid

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# 5-minute timeout — local LLMs on mid-range GPUs can be slow
AGENT_TIMEOUT_SECONDS = 300


class AgentServiceError(Exception):
    """Raised when the agent call fails for any reason."""
    pass


class AgentService:

    @staticmethod
    def _read_resume_bytes(resume) -> bytes:
        """
        Read PDF bytes from Django's file storage.

        FileField.open() works regardless of whether the file is stored
        locally, on S3 (Phase production), or any other Django storage backend.
        """
        try:
            with resume.file.open("rb") as f:
                return f.read()
        except Exception as e:
            raise AgentServiceError(f"Could not read resume file from storage: {e}")

    @classmethod
    def trigger_run(cls, application, resume) -> dict:
        """
        Call FastAPI to run the agent pipeline.

        Args:
            application: Django Application model instance (must have .agent_run_id set)
            resume:      Django Resume model instance (must have .file and .raw_text)

        Returns:
            dict — the AgentRunResponse JSON parsed from FastAPI's response

        Raises:
            AgentServiceError — on timeout, HTTP error, or unreachable service
        """
        run_id = str(application.agent_run_id)
        logger.info(
            f"[{run_id}] Calling FastAPI agent — "
            f"application={application.id} user={application.user.id}"
        )

        # Read + encode PDF
        pdf_bytes = cls._read_resume_bytes(resume)
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        logger.debug(
            f"[{run_id}] Resume PDF encoded: "
            f"{len(pdf_bytes)} bytes → {len(pdf_base64)} chars base64"
        )

        payload = {
            "run_id": run_id,
            "user_id": str(application.user.id),
            "application_id": str(application.id),
            "jd_raw": application.job_description,
            "jd_url": application.job_url or None,
            "resume_pdf_base64": pdf_base64,
            "resume_raw_text": resume.raw_text or "",
            "user_tone": application.tone,
        }

        fastapi_url = getattr(settings, "FASTAPI_URL", "http://localhost:8001")
        internal_secret = getattr(settings, "INTERNAL_API_SECRET", "")

        try:
            with httpx.Client(timeout=AGENT_TIMEOUT_SECONDS) as client:
                response = client.post(
                    f"{fastapi_url}/api/agent/run",
                    json=payload,
                    headers={"X-Internal-Token": internal_secret},
                )

            if response.status_code == 400:
                raise AgentServiceError(
                    f"Agent rejected the request (400): {response.text[:200]}"
                )
            if response.status_code == 401:
                raise AgentServiceError(
                    "Agent rejected the request (401 Unauthorized). "
                    "Check INTERNAL_API_SECRET matches between Django and FastAPI."
                )
            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException:
            raise AgentServiceError(
                f"Agent timed out after {AGENT_TIMEOUT_SECONDS}s. "
                "This can happen with large models on CPU-only inference."
            )
        except httpx.ConnectError:
            raise AgentServiceError(
                f"Could not connect to FastAPI agent at {fastapi_url}. "
                "Is the agent service running?"
            )
        except httpx.HTTPStatusError as e:
            raise AgentServiceError(
                f"Agent returned HTTP {e.response.status_code}: {e.response.text[:200]}"
            )
        except AgentServiceError:
            raise  # re-raise our own errors without wrapping
        except Exception as e:
            raise AgentServiceError(f"Unexpected error calling agent: {type(e).__name__}: {e}")
