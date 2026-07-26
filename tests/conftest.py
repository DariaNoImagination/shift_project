import pytest
import sys
from pathlib import Path
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from main import app
from database import get_db, Base, hash_password
from db_models import User, UserRole

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool
)

TestingSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True, scope="function")
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_user():
    async with TestingSessionLocal() as db:
        user = User(
            email="test@example.com",
            username="testuser",
            full_name="Test User",
            hashed_password=hash_password("testpass123"),
            role=UserRole.EMPLOYEE,
            is_active=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest.fixture
async def test_admin():
    async with TestingSessionLocal() as db:
        admin = User(
            email="admin@test.com",
            username="admin",
            full_name="Admin User",
            hashed_password=hash_password("adminpass123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin


@pytest.fixture
async def user_token(client, test_user):
    response = await client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "testpass123"}
    )
    return response.cookies.get("access_token")


@pytest.fixture
async def admin_token(client, test_admin):
    response = await client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "adminpass123"}
    )
    return response.cookies.get("access_token")



@pytest.fixture
async def auth_client(client, user_token) -> AsyncGenerator[AsyncClient, None]:
    client.cookies.set("access_token", user_token)
    yield client