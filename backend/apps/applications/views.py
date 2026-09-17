import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Application, AgentRun
from .serializers import (
    ApplicationCreateSerializer,
    ApplicationSerializer,
    AgentRunSerializer,
)

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def application_list_create(request: Request) -> Response:
    if request.method == "GET":
        applications = Application.objects.filter(user=request.user).select_related("resume")
        serializer = ApplicationSerializer(applications, many=True)
        return Response(serializer.data)

    if request.method == "POST":
        serializer = ApplicationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        application = serializer.save(user=request.user)
        logger.info(f"Application created: {application.id} by {request.user.email}")

        # Phase 3+: kick off agent run here via FastAPI call
        # For now, return the created application
        return Response(
            ApplicationSerializer(application).data,
            status=status.HTTP_201_CREATED,
        )


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
