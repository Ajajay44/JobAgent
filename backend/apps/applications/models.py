"""
Application and AgentRun models.
"""
import uuid
from django.db import models
from django.conf import settings


class ApplicationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class Application(models.Model):
    """
    Represents one job application attempt.
    Links a user, their resume, and a job description.
    Tracks the agent run and its results.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    resume = models.ForeignKey(
        "resumes.Resume",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
    )

    # Job details — filled by user
    job_description = models.TextField()
    job_url = models.URLField(blank=True, help_text="Optional job posting URL for company research")
    company_name = models.CharField(max_length=255, blank=True)
    role_title = models.CharField(max_length=255, blank=True)
    tone = models.CharField(
        max_length=50,
        default="professional",
        help_text="e.g. professional, conversational, enthusiastic",
    )

    # Agent tracking
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
        db_index=True,
    )
    agent_run_id = models.UUIDField(null=True, blank=True)

    # Results — populated by package_store node (Phase 9)
    result_resume_pdf = models.FileField(upload_to="results/resumes/", null=True, blank=True)
    result_cover_letter_pdf = models.FileField(upload_to="results/cover_letters/", null=True, blank=True)
    result_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Structured output: rewritten resume, cover letter, emails",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "applications"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email} — {self.role_title or 'Application'} ({self.status})"


class AgentRun(models.Model):
    """
    Observability record for a single agent execution.
    One-to-one with Application.
    Every node execution is logged here for debugging.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name="agent_run",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_runs",
    )

    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
    )
    current_node = models.CharField(max_length=100, blank=True)

    # JSONB columns for structured logging
    node_log = models.JSONField(
        default=list,
        help_text="[{node, status, started_at, ended_at, duration_ms}, ...]",
    )
    error_log = models.JSONField(
        default=list,
        help_text="List of error strings encountered during the run",
    )

    retry_count = models.IntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_runs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run {self.id} [{self.status}]"
