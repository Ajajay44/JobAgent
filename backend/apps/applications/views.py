import uuid
import logging
from datetime import datetime, timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Application, AgentRun, ApplicationStatus
from .serializers import (
    ApplicationCreateSerializer,
    ApplicationSerializer,
    AgentRunSerializer,
)
from .services import AgentService, AgentServiceError

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def application_list_create(request: Request) -> Response:
    if request.method == "GET":
        applications = Application.objects.filter(user=request.user).select_related("resume")
        return Response(ApplicationSerializer(applications, many=True).data)

    if request.method == "POST":
        serializer = ApplicationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # ── Create application record ──────────────────────────────────────
        run_id = uuid.uuid4()
        application = serializer.save(
            user=request.user,
            agent_run_id=run_id,
            status=ApplicationStatus.PROCESSING,
        )
        logger.info(
            f"Application created: {application.id} by {request.user.email} "
            f"run_id={run_id}"
        )

        # ── Trigger agent ──────────────────────────────────────────────────
        resume = application.resume
        if not resume:
            # No resume attached — mark pending, user must re-submit with resume
            application.status = ApplicationStatus.PENDING
            application.save(update_fields=["status"])
            logger.warning(f"Application {application.id} has no resume — skipping agent call")
            return Response(
                {**ApplicationSerializer(application).data, "warning": "No resume attached. Agent not started."},
                status=status.HTTP_201_CREATED,
            )

        # Create the AgentRun record immediately (shows "processing" to user)
        agent_run = AgentRun.objects.create(
            application=application,
            user=request.user,
            status=ApplicationStatus.PROCESSING,
            current_node="starting",
            started_at=datetime.now(tz=timezone.utc),
        )

        try:
            result = AgentService.trigger_run(application, resume)
            _handle_agent_success(application, agent_run, result)

        except AgentServiceError as e:
            _handle_agent_failure(application, agent_run, str(e))
            logger.error(f"Agent call failed for {application.id}: {e}")

        return Response(
            ApplicationSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


def _handle_agent_success(application: Application, agent_run: AgentRun, result: dict) -> None:
    """Update Application and AgentRun after a successful agent call."""
    run_status = result.get("status", "failed")
    steps_completed = result.get("steps_completed", [])
    errors = result.get("errors", [])
    duration_ms = result.get("duration_ms", 0)

    # Determine Application status
    app_status = (
        ApplicationStatus.COMPLETED
        if run_status in ("completed", "partial")
        else ApplicationStatus.FAILED
    )

    # Collect result data (all parsed outputs)
    result_data = {
        "jd_parsed": result.get("jd_parsed"),
        "resume_parsed": result.get("resume_parsed"),
        "skill_alignment": result.get("skill_alignment"),
        "company_intelligence": result.get("company_intelligence"),
        "resume_rewritten": result.get("resume_rewritten"),
        "cover_letter_content": result.get("cover_letter_content"),
        "cold_email_variants": result.get("cold_email_variants"),
        "linkedin_referral": result.get("linkedin_referral"),
    }


    # Build observability log entry
    node_log_entry = {
        "run_status": run_status,
        "steps_completed": steps_completed,
        "duration_ms": duration_ms,
    }

    # Update Application
    application.status = app_status
    application.result_data = result_data
    application.save(update_fields=["status", "result_data"])

    # Update AgentRun
    agent_run.status = app_status
    agent_run.current_node = steps_completed[-1] if steps_completed else ""
    agent_run.node_log = [node_log_entry]
    agent_run.error_log = errors
    agent_run.completed_at = datetime.now(tz=timezone.utc)
    agent_run.save(update_fields=[
        "status", "current_node", "node_log", "error_log", "completed_at"
    ])

    logger.info(
        f"Application {application.id} updated — "
        f"status={app_status} steps={steps_completed}"
    )


def _handle_agent_failure(application: Application, agent_run: AgentRun, error_msg: str) -> None:
    """Mark Application and AgentRun as failed."""
    application.status = ApplicationStatus.FAILED
    application.save(update_fields=["status"])

    agent_run.status = ApplicationStatus.FAILED
    agent_run.error_log = [error_msg]
    agent_run.completed_at = datetime.now(tz=timezone.utc)
    agent_run.save(update_fields=["status", "error_log", "completed_at"])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def application_detail(request: Request, pk: str) -> Response:
    try:
        application = Application.objects.get(pk=pk, user=request.user)
    except Application.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(ApplicationSerializer(application).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def application_run_status(request: Request, pk: str) -> Response:
    """Return the agent run log for a given application."""
    try:
        application = Application.objects.get(pk=pk, user=request.user)
    except Application.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        run = application.agent_run
        return Response(AgentRunSerializer(run).data)
    except AgentRun.DoesNotExist:
        return Response(
            {"detail": "No agent run found for this application."},
            status=status.HTTP_404_NOT_FOUND,
        )

