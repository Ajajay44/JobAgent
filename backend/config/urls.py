"""
URL configuration for JobUndo Django project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django admin
    path("admin/", admin.site.urls),

    # Health check (public — used by Docker healthcheck and load balancers)
    path("api/health/", include("apps.accounts.urls_health")),

    # Auth endpoints: /api/auth/register/, /api/auth/login/, etc.
    path("api/auth/", include("apps.accounts.urls")),

    # Resume management: /api/resumes/
    path("api/resumes/", include("apps.resumes.urls")),

    # Application CRUD: /api/applications/
    path("api/applications/", include("apps.applications.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
