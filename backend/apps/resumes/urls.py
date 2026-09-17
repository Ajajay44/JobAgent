from django.urls import path
from . import views

urlpatterns = [
    path("", views.resume_list_create, name="resume-list-create"),
    path("<uuid:pk>/", views.resume_detail, name="resume-detail"),
]
