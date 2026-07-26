import pytest
from httpx import AsyncClient
pytestmark = pytest.mark.asyncio

class TestAuth:
    pytestmark = pytest.mark.asyncio
    async def test_login_invalid_password(self, client: AsyncClient, test_user):
        """Тест входа с неверным паролем"""
        response = await client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.text

    async def test_login_user_not_found(self, client: AsyncClient):
        """Тест входа с несуществующим пользователем"""
        response = await client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"}
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.text

    async def test_logout(self, client: AsyncClient, user_token):
        """Тест выхода из системы"""
        response = await client.post(
            "/auth/logout",
            cookies={"access_token": user_token}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Logout successful"
        # Проверяем, что cookie удалена
        assert "access_token" not in response.cookies or response.cookies.get("access_token") == ""

    async def test_me_authenticated(self, client: AsyncClient, user_token):
        """Тест получения информации о текущем пользователе"""
        response = await client.get(
            "/auth/me",
            cookies={"access_token": user_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"

    async def test_me_unauthenticated(self, client: AsyncClient):
        """Тест получения информации без авторизации"""
        response = await client.get("/auth/me")
        assert response.status_code == 401
        assert "Not authenticated" in response.text

    async def test_check_auth_valid(self, client: AsyncClient, user_token):
        """Тест проверки валидного токена"""
        response = await client.get(
            "/auth/check",
            cookies={"access_token": user_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"]["email"] == "test@example.com"

    async def test_check_auth_invalid(self, client: AsyncClient):
        """Тест проверки невалидного токена"""
        response = await client.get(
            "/auth/check",
            cookies={"access_token": "invalid.token.here"}
        )
        assert response.status_code == 401
        data = response.json()
        assert data["authenticated"] is False