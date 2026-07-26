# database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from base import Base  
import os
from datetime import datetime, date, time
from db_models import User, MeetingRoom, TimeSlot, Booking, UserRole, BookingStatus
from sqlalchemy import select

DATABASE_URL = os.getenv(
    "DATABASE_URL_ASYNC",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/booking_db"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


async def init_db():
    """Создание таблиц и заполнение тестовыми данными"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Заполняем тестовыми данными
    async with AsyncSessionLocal() as db:
        await init_test_data(db)


async def init_test_data(db: AsyncSession):
    """Инициализация тестовых данных"""


    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none():
        return


    admin = User(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        hashed_password=hash_password("admin123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin)

    employee = User(
        email="employee@example.com",
        username="employee",
        full_name="Employee User",
        hashed_password=hash_password("employee123"),
        role=UserRole.EMPLOYEE,
        is_active=True
    )
    db.add(employee)

    await db.flush()

    slots = [
        ("09:00", "11:00"),
        ("11:00", "13:00"),
        ("13:00", "15:00"),
        ("15:00", "17:00"),
        ("17:00", "19:00"),
    ]


    room_a = MeetingRoom(
        name="Переговорная А",
        description="Большая комната для встреч",
        capacity=10,
        location="3-й этаж",
        is_active=True
    )
    db.add(room_a)
    await db.flush()

    for start, end in slots:
        slot = TimeSlot(
            room_id=room_a.id,
            start_time=datetime.strptime(start, "%H:%M").time(),
            end_time=datetime.strptime(end, "%H:%M").time(),
            is_available=True
        )
        db.add(slot)


    room_b = MeetingRoom(
        name="Переговорная Б",
        description="Маленькая комната для встреч",
        capacity=4,
        location="2-й этаж",
        is_active=True
    )
    db.add(room_b)
    await db.flush()

    for start, end in slots:
        slot = TimeSlot(
            room_id=room_b.id,
            start_time=datetime.strptime(start, "%H:%M").time(),
            end_time=datetime.strptime(end, "%H:%M").time(),
            is_available=True
        )
        db.add(slot)
    await db.commit()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()