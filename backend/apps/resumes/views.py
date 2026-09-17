import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Resume
from .serializers import ResumeUploadSerializer, ResumeSerializer

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def resume_list_create(request: Request) -> Response:
    if request.method == "GET":
        resumes = Resume.objects.filter(user=request.user, is_active=True)
        serializer = ResumeSerializer(resumes, many=True)
        return Response(serializer.data)

    # POST — upload a new resume
    if request.method == "POST":
        serializer = ResumeUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        resume = serializer.save(user=request.user)
        logger.info(f"Resume uploaded: {resume.id} by {request.user.email}")
        return Response(ResumeSerializer(resume).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def resume_detail(request: Request, pk: str) -> Response:
    try:
        resume = Resume.objects.get(pk=pk, user=request.user)
    except Resume.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(ResumeSerializer(resume).data)

    if request.method == "DELETE":
        # Soft delete — preserve the file for audit, just mark inactive
        resume.is_active = False
        resume.save(update_fields=["is_active"])
        logger.info(f"Resume soft-deleted: {resume.id} by {request.user.email}")
        return Response(status=status.HTTP_204_NO_CONTENT)
