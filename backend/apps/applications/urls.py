from django.urls import path
from . import views

urlpatterns = [
    path("", views.application_list_create, name="application-list-create"),
    path("<uuid:pk>/", views.application_detail, name="application-detail"),
    path("<uuid:pk>/run/", views.application_run_status, name="application-run-status"),
]
