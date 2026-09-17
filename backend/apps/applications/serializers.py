import logging
from rest_framework import serializers
from .models import Application, AgentRun

logger = logging.getLogger(__name__)


class ApplicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = (
            "id", "resume", "job_description", "job_url",
            "company_name", "role_title", "tone",
        )
        read_only_fields = ("id",)

    def validate_job_description(self, value: str) -> str:
        value = value.strip()
        if len(value) < 50:
            raise serializers.ValidationError(
                "Job description is too short. Please paste the full job posting."
            )
        if len(value) > 20_000:
            raise serializers.ValidationError(
                "Job description is too long (max 20,000 characters)."
            )
        return value


class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = (
            "id", "resume", "job_description", "job_url",
            "company_name", "role_title", "tone",
            "status", "agent_run_id", "result_data",
            "created_at", "updated_at",
        )
        read_only_fields = fields


class AgentRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentRun
        fields = (
            "id", "status", "current_node", "node_log",
            "error_log", "retry_count", "started_at", "completed_at",
        )
        read_only_fields = fields
