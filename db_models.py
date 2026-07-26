from sqlalchemy import Integer, String, DateTime, Boolean, Date, Time, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from base import Base  
from typing import Optional, List
from datetime import datetime, date, time
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class BookingStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.EMPLOYEE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class MeetingRoom(Base):
    __tablename__ = "meeting_rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    time_slots: Mapped[List["TimeSlot"]] = relationship("TimeSlot", back_populates="room", cascade="all, delete-orphan")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="room")

    def __repr__(self):
        return f"<MeetingRoom(id={self.id}, name={self.name}, capacity={self.capacity})>"


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("meeting_rooms.id", ondelete="CASCADE"), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    room: Mapped["MeetingRoom"] = relationship("MeetingRoom", back_populates="time_slots")
    bookings: Mapped[List["Booking"]] = relationship("Booking", back_populates="time_slot")

    __table_args__ = (
        UniqueConstraint('room_id', 'start_time', 'end_time', name='uq_room_timeslot'),
    )

    def __repr__(self):
        return f"<TimeSlot(id={self.id}, room_id={self.room_id}, {self.start_time}-{self.end_time})>"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("meeting_rooms.id", ondelete="CASCADE"), nullable=False)
    time_slot_id: Mapped[int] = mapped_column(Integer, ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    booking_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    room: Mapped["MeetingRoom"] = relationship("MeetingRoom", back_populates="bookings")
    time_slot: Mapped["TimeSlot"] = relationship("TimeSlot", back_populates="bookings")
    user: Mapped["User"] = relationship("User", back_populates="bookings")

    __table_args__ = (
        UniqueConstraint('room_id', 'time_slot_id', 'booking_date', name='uq_room_slot_date'),
    )

    def __repr__(self):
        return f"<Booking(id={self.id}, room_id={self.room_id}, user_id={self.user_id}, date={self.booking_date})>"