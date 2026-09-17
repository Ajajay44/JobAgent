"""
Health check endpoint — public, no auth required.
Used by Docker healthcheck, nginx, and load balancers.
"""
import logging
from django.db import connection
from django.db.utils import OperationalError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """
    Returns system health status.
    Checks: Django itself, database connectivity.
    """
    db_ok = False
    try:
        connection.ensure_connection()
        db_ok = True
    except OperationalError as e:
        logger.error(f"Health check — DB failure: {e}")

    status_code = 200 if db_ok else 503
    return Response(
        {
            "status": "healthy" if db_ok else "degraded",
            "service": "jobundo-django",
            "checks": {
                "database": "ok" if db_ok else "unreachable",
            },
        },
        status=status_code,
    )
