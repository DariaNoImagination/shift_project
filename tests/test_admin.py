import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

class TestAdmin:

    async def test_admin_dashboard_page_unauthenticated(self, client: AsyncClient):
        """Тест страницы админ-панели без авторизации"""
        response = await client.get("/admin")
        assert response.status_code == 307
        assert "/login" in response.headers.get("location", "")

    async def test_admin_api_dashboard_unauthorized(self, client: AsyncClient):
        """Тест API админ-панели без авторизации"""
        response = await client.get("/api/admin/statistics")
        assert response.status_code == 401
        assert "Not authenticated" in response.text

    async def test_admin_api_dashboard_as_user(self, auth_client: AsyncClient):
        """Тест API админ-панели обычным пользователем"""
        response = await auth_client.get("/api/admin/statistics")
        assert response.status_code == 403


    async def test_admin_api_dashboard_as_admin(self, client: AsyncClient, admin_token):
        """Тест API админ-панели администратором"""
        client.cookies.set("access_token", admin_token)
        response = await client.get("/api/admin/statistics")
        assert response.status_code == 200
        data = response.json()
        assert "admin" in data
        assert "statistics" in data
        assert "bookings_by_date" in data
        assert "all_bookings" in data
        assert data["admin"]["email"] == "admin@test.com"