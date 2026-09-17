"""
Resume model — stores uploaded PDFs and their parsed metadata.
"""
import uuid
from django.db import models
from django.conf import settings


def resume_upload_path(instance: "Resume", filename: str) -> str:
    """Isolate each user's uploads in their own directory."""
    return f"resumes/{instance.user.id}/{uuid.uuid4()}.pdf"


class Resume(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resumes",
    )

    # File storage
    file = models.FileField(upload_to=resume_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(help_text="File size in bytes")

    # Parsed content — populated by Phase 2 (parse_resume node)
    raw_text = models.TextField(blank=True, help_text="Extracted plain text from PDF")
    parsed_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Structured resume data (contact, experience, skills, etc.)",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "resumes"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} — {self.original_filename}"
