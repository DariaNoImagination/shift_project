# tests/test_dashboard.py
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestDashboard:
    """Тесты дашборда"""

    async def test_dashboard_page_unauthenticated(self, client: AsyncClient):
        """Тест страницы дашборда без авторизации"""
        response = await client.get("/dashboard")
        assert response.status_code == 307
        assert "/login" in response.headers.get("location", "")


    async def test_api_dashboard_unauthorized(self, client: AsyncClient):
        """Тест API дашборда без авторизации"""
        response = await client.get("/api/rooms/availability")
        assert response.status_code == 401
        data = response.json()
        assert data["error"] == "Not authenticated"

    async def test_api_dashboard_authenticated(self, auth_client: AsyncClient):
        """Тест API дашборда авторизованным пользователем"""
        response = await auth_client.get("/api/rooms/availability")
        assert response.status_code == 200
        data = response.json()
        assert "user" in data
        assert "rooms_availability" in data
        assert "statistics" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["role"] == "employee"