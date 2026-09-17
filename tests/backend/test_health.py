"""
Django health check tests.

Run with:
    docker exec jobundo_django python manage.py test tests.backend.test_health
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import TestCase, Client


class HealthCheckTest(TestCase):
    """Test the /api/health/ endpoint."""

    def setUp(self):
        self.client = Client()

    def test_health_returns_200(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)

    def test_health_json_structure(self):
        response = self.client.get("/api/health/")
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("service", data)
        self.assertIn("checks", data)

    def test_health_service_name(self):
        response = self.client.get("/api/health/")
        data = response.json()
        self.assertEqual(data["service"], "jobundo-django")

    def test_health_db_check_present(self):
        response = self.client.get("/api/health/")
        data = response.json()
        self.assertIn("database", data["checks"])
