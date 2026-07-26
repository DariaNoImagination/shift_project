from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pathlib import Path
from datetime import date
from typing import Optional

from routers import authJWT, bookings, users
from db_models import User as DBUser, MeetingRoom as DBMeetingRoom, TimeSlot as DBTimeSlot, Booking as DBBooking
from models import User, UserRole
from dependencies import get_current_user
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from contextlib import asynccontextmanager
from database import init_db, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Booking Service API",
    description="Service for booking meeting rooms",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(authJWT.router)
app.include_router(bookings.router)
app.include_router(users.router)


TEMPLATES_DIR = Path(__file__).parent / "templates"


def read_html(filename: str) -> str:
    file_path = TEMPLATES_DIR / filename
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Страница не найдена</h1>"



@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(content=read_html("login.html"))


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            token = auth_header.replace("Bearer ", "")
    if not token:
        return RedirectResponse(url="/login")
    try:
        from auth import decode_token
        payload = decode_token(token)
        user_id = payload.get("user_id")
        async for db in get_db():
            user = await db.get(DBUser, user_id)
            if not user:
                return RedirectResponse(url="/login")
            break
    except Exception as e:
        print(f"Ошибка проверки токена: {e}")
        return RedirectResponse(url="/login")
    return HTMLResponse(content=read_html("dashboard.html"))


@app.get("/admin")
async def admin_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            token = auth_header.replace("Bearer ", "")
    if not token:
        return RedirectResponse(url="/login")
    try:
        from auth import decode_token
        payload = decode_token(token)
        user_id = payload.get("user_id")
        async for db in get_db():
            user = await db.get(DBUser, user_id)
            if not user or user.role != UserRole.ADMIN:
                return RedirectResponse(url="/dashboard")
            break
    except Exception as e:
        print(f"Ошибка проверки токена: {e}")
        return RedirectResponse(url="/login")
    return HTMLResponse(content=read_html("admin_dashboard.html"))


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response


@app.get("/")
async def root():
    return RedirectResponse(url="/login")



@app.get("/api/rooms/availability")
async def get_rooms_availability(
    booking_date: Optional[str] = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Данные для дашборда (доступность комнат)"""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header:
            token = auth_header.replace("Bearer ", "")
    if not token:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated", "login_url": "/login"}
        )

    try:
        from auth import decode_token
        payload = decode_token(token)
        user_id = payload.get("user_id")
        current_user = await db.get(DBUser, user_id)
        if not current_user:
            return JSONResponse(
                status_code=401,
                content={"error": "User not found", "login_url": "/login"}
            )
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid token", "login_url": "/login"}
        )

    booking_date_obj = date.today() if not booking_date else date.fromisoformat(booking_date)

    rooms_result = await db.execute(
        select(DBMeetingRoom).where(DBMeetingRoom.is_active == True)
    )
    active_rooms = rooms_result.scalars().all()

    rooms_availability = []
    for room in active_rooms:
        slots_result = await db.execute(
            select(DBTimeSlot).where(DBTimeSlot.room_id == room.id)
        )
        room_slots = slots_result.scalars().all()

        bookings_result = await db.execute(
            select(DBBooking).where(
                DBBooking.room_id == room.id,
                DBBooking.booking_date == booking_date_obj,
                DBBooking.status != "cancelled"
            )
        )
        day_bookings = bookings_result.scalars().all()

        booked_slot_ids = [b.time_slot_id for b in day_bookings]
        available_slots = [s for s in room_slots if s.id not in booked_slot_ids]

        rooms_availability.append({
            "room": room,
            "available_slots": available_slots,
            "booked_slots": day_bookings,
            "total_slots": len(room_slots),
            "available_count": len(available_slots)
        })

    my_bookings_result = await db.execute(
        select(DBBooking).where(
            DBBooking.user_id == current_user.id,
            DBBooking.status != "cancelled",
            DBBooking.booking_date >= date.today()
        ).order_by(DBBooking.booking_date)
    )
    my_bookings = my_bookings_result.scalars().all()

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role
        },
        "booking_date": booking_date_obj.isoformat(),
        "rooms_availability": rooms_availability,
        "my_bookings": my_bookings,
        "statistics": {
            "total_rooms": len(active_rooms),
            "total_available_slots": sum(r["available_count"] for r in rooms_availability),
            "my_bookings_count": len(my_bookings)
        },
        "is_admin": current_user.role == UserRole.ADMIN
    }


@app.get("/api/admin/statistics")
async def get_admin_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    users_result = await db.execute(select(DBUser))
    total_users = len(users_result.scalars().all())

    rooms_result = await db.execute(
        select(DBMeetingRoom).where(DBMeetingRoom.is_active == True)
    )
    total_rooms = len(rooms_result.scalars().all())

    bookings_result = await db.execute(
        select(DBBooking).where(DBBooking.status != "cancelled")
    )
    all_bookings = bookings_result.scalars().all()
    total_bookings = len(all_bookings)
    active_bookings = len([b for b in all_bookings if b.status == "active"])

    bookings_by_date = {}
    for b in all_bookings:
        date_str = b.booking_date.isoformat()
        bookings_by_date[date_str] = bookings_by_date.get(date_str, 0) + 1

    return {
        "admin": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email
        },
        "statistics": {
            "total_users": total_users,
            "total_rooms": total_rooms,
            "total_bookings": total_bookings,
            "active_bookings": active_bookings
        },
        "bookings_by_date": bookings_by_date,
        "all_bookings": [
            {
                "id": b.id,
                "room_id": b.room_id,
                "time_slot_id": b.time_slot_id,
                "user_id": b.user_id,
                "booking_date": b.booking_date.isoformat(),
                "title": b.title,
                "status": b.status.value if hasattr(b.status, 'value') else str(b.status),
                "created_at": b.created_at.isoformat(),
                "updated_at": b.updated_at.isoformat()
            }
            for b in sorted(all_bookings, key=lambda x: x.created_at, reverse=True)[:50]
        ]
    }


@app.get("/auth/me")
async def auth_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role
    }