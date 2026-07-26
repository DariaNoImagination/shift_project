from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime, date, time
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"

class BookingStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class User(BaseModel):
    id: int
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=200)
    hashed_password: str
    role: UserRole = UserRole.EMPLOYEE
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

class TimeSlot(BaseModel):
    id: int
    room_id: int
    start_time: time
    end_time: time
    is_available: bool = True

    @field_validator('end_time')
    def end_time_must_be_after_start(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be after start_time')
        return v


class MeetingRoom(BaseModel):
    id: int
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    capacity: int = Field(..., ge=1, le=100)
    location: Optional[str] = Field(None, max_length=200)
    is_active: bool = True
    created_at: datetime
    time_slots: List[TimeSlot] = []


class Booking(BaseModel):
    id: int
    room_id: int
    time_slot_id: int
    user_id: int
    booking_date: date
    title: Optional[str] = Field(None, max_length=200)
    status: BookingStatus = BookingStatus.ACTIVE
    created_at: datetime
    updated_at: datetime


class BookingCreate(BaseModel):
    room_id: int
    time_slot_id: int
    booking_date: date
    title: Optional[str] = Field(None, max_length=200)

    @field_validator('booking_date')
    def booking_date_must_be_future(cls, v):
        if v < date.today():
            raise ValueError('booking_date must be today or in future')
        return v


class BookingUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    status: Optional[BookingStatus] = None


class RoomAvailability(BaseModel):
    room_id: int
    room_name: str
    booking_date: date
    capacity: int
    available_slots: List[TimeSlot] = []
    booked_slots: List[Booking] = []

class Movie(BaseModel):
    name: str
    plot: str
    genres: List[str]
    casts: List[str]

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: int
    username: str
    role: str
    exp: Optional[int] = None

class BookingCreate(BaseModel):
    room_id: int = Field(..., description="ID комнаты")
    time_slot_id: int = Field(..., description="ID временного слота")
    booking_date: date = Field(..., description="Дата бронирования")
    title: Optional[str] = Field(None, max_length=200, description="Название встречи")

    @field_validator('booking_date')
    def booking_date_must_be_future(cls, v):
        if v < date.today():
            raise ValueError('booking_date must be today or in future')
        return v

class BookingUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    status: Optional[BookingStatus] = None