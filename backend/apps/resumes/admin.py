from django.contrib import admin
from .models import Resume


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("user", "original_filename", "file_size", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("user__email", "original_filename")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
