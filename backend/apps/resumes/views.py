import io
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Resume
from .serializers import ResumeUploadSerializer, ResumeSerializer

logger = logging.getLogger(__name__)


def _extract_pdf_text(file) -> str:
    """
    Extract plain text from an uploaded PDF file using pdfplumber.
    Falls back to PyPDF2 if pdfplumber fails.

    Called immediately on upload so the text is stored in the DB
    and available to the agent without re-reading the file.
    """
    text_pages = []

    # Primary: pdfplumber (better at complex layouts)
    try:
        import pdfplumber
        file.seek(0)
        with pdfplumber.open(io.BytesIO(file.read())) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text and text.strip():
                    text_pages.append(text.strip())
        file.seek(0)
        if text_pages:
            logger.debug(f"pdfplumber extracted {len(text_pages)} pages")
            return "\n\n".join(text_pages)
    except Exception as e:
        logger.warning(f"pdfplumber extraction failed: {e} — trying PyPDF2")
        file.seek(0)

    # Fallback: PyPDF2
    try:
        import PyPDF2
        file.seek(0)
        reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                text_pages.append(text.strip())
        file.seek(0)
        if text_pages:
            logger.debug(f"PyPDF2 extracted {len(text_pages)} pages")
            return "\n\n".join(text_pages)
    except Exception as e:
        logger.error(f"PyPDF2 fallback failed: {e}")
        file.seek(0)

    return ""


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

        # Extract text before saving (file is still in memory)
        uploaded_file = request.FILES.get("file")
        raw_text = ""
        if uploaded_file:
            raw_text = _extract_pdf_text(uploaded_file)
            if not raw_text:
                logger.warning(
                    f"Could not extract text from uploaded PDF: {uploaded_file.name}. "
                    "May be image-based. Upload accepted but parsing may fail."
                )

        resume = serializer.save(user=request.user, raw_text=raw_text)
        logger.info(
            f"Resume uploaded: {resume.id} by {request.user.email} "
            f"({len(raw_text)} chars extracted)"
        )
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

