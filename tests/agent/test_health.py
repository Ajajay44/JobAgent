"""
FastAPI agent service health check tests.

Run with:
    docker exec jobundo_fastapi python -m pytest tests/agent/test_health.py -v
"""
import pytest
from httpx import AsyncClient, ASGITransport

# Add agent dir to path
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../agent'))


@pytest.fixture
def app():
    from main import app
    return app


@pytest.mark.asyncio
async def test_health_returns_200_or_503(app):
    """Health should always return a response (200 healthy or 503 degraded)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code in (200, 503)


@pytest.mark.asyncio
async def test_health_json_structure(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_health_service_name(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    data = response.json()
    assert data["service"] == "jobundo-agent"


@pytest.mark.asyncio
async def test_agent_run_requires_auth(app):
    """Agent run endpoint must reject requests without internal token."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/agent/run")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_agent_run_with_wrong_token(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/agent/run",
            headers={"X-Internal-Token": "wrong-token"},
        )
    assert response.status_code == 401
