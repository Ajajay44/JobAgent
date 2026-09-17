from django.contrib import admin
from .models import Application, AgentRun


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "role_title", "company_name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__email", "role_title", "company_name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "agent_run_id")


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "status", "current_node", "retry_count", "created_at")
    list_filter = ("status",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
