import logging
from django.contrib.auth import get_user_model, authenticate
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request: Request) -> Response:
    """Create a new user account and return an auth token."""
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.save()
    token, _ = Token.objects.get_or_create(user=user)
    logger.info(f"New user registered: {user.email}")

    return Response(
        {
            "token": token.key,
            "user": UserSerializer(user).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request: Request) -> Response:
    """Authenticate and return a token."""
    email = request.data.get("email", "").strip()
    password = request.data.get("password", "")

    if not email or not password:
        return Response(
            {"detail": "Email and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=email, password=password)
    if not user:
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    token, _ = Token.objects.get_or_create(user=user)
    logger.info(f"User logged in: {user.email}")

    return Response(
        {
            "token": token.key,
            "user": UserSerializer(user).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request: Request) -> Response:
    """Invalidate the current token."""
    try:
        request.user.auth_token.delete()
    except Exception:
        pass
    logger.info(f"User logged out: {request.user.email}")
    return Response({"detail": "Logged out successfully."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request: Request) -> Response:
    """Return the authenticated user's profile."""
    return Response(UserSerializer(request.user).data)
