from django.urls import path
from .views_health import health

urlpatterns = [
    path("", health, name="health"),
]
