import logging
from rest_framework import serializers
from .models import Resume

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {"application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class ResumeUploadSerializer(serializers.ModelSerializer):
    """Handles resume file upload with strict validation."""

    class Meta:
        model = Resume
        fields = ("id", "file", "original_filename", "file_size", "created_at")
        read_only_fields = ("id", "original_filename", "file_size", "created_at")

    def validate_file(self, file):
        # Validate MIME type (PDF only)
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise serializers.ValidationError(
                "Only PDF files are accepted. "
                f"Received: {file.content_type}"
            )
        # Validate file size
        if file.size > MAX_FILE_SIZE:
            raise serializers.ValidationError(
                f"File too large. Maximum allowed size is 10 MB. "
                f"Received: {file.size / 1024 / 1024:.1f} MB"
            )
        # Validate PDF magic bytes (first 4 bytes should be %PDF)
        header = file.read(4)
        file.seek(0)
        if header != b"%PDF":
            raise serializers.ValidationError(
                "File does not appear to be a valid PDF."
            )
        return file

    def create(self, validated_data: dict) -> Resume:
        file = validated_data["file"]
        validated_data["original_filename"] = file.name
        validated_data["file_size"] = file.size
        return super().create(validated_data)


class ResumeSerializer(serializers.ModelSerializer):
    """Read-only resume representation."""

    class Meta:
        model = Resume
        fields = (
            "id", "original_filename", "file_size",
            "raw_text", "parsed_data", "is_active", "created_at",
        )
        read_only_fields = fields
