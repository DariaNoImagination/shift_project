from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError

from models import Booking as PydanticBooking, BookingCreate, BookingUpdate, BookingStatus, User as PydanticUser, \
    UserRole
from db_models import Booking as DBBooking, MeetingRoom as DBMeetingRoom, TimeSlot as DBTimeSlot, User as DBUser
from database import get_db
from dependencies import get_current_user


router = APIRouter(prefix="/bookings", tags=["bookings"])


def booking_to_pydantic(db_booking: DBBooking) -> PydanticBooking:
    """Преобразование SQLAlchemy модели в Pydantic"""
    return PydanticBooking(
        id=db_booking.id,
        room_id=db_booking.room_id,
        time_slot_id=db_booking.time_slot_id,
        user_id=db_booking.user_id,
        booking_date=db_booking.booking_date,
        title=db_booking.title,
        status=db_booking.status,
        created_at=db_booking.created_at,
        updated_at=db_booking.updated_at
    )


@router.get("/", response_model=List[PydanticBooking])
async def get_bookings(
        user_id: Optional[int] = None,
        room_id: Optional[int] = None,
        booking_date: Optional[date] = None,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получение списка бронирований с фильтрами"""
    try:
        query = select(DBBooking)

        if current_user.role != UserRole.ADMIN:
            query = query.where(DBBooking.user_id == current_user.id)
        if user_id and current_user.role == UserRole.ADMIN:
            query = query.where(DBBooking.user_id == user_id)
        if room_id:
            query = query.where(DBBooking.room_id == room_id)
        if booking_date:
            query = query.where(DBBooking.booking_date == booking_date)

        query = query.order_by(DBBooking.booking_date)

        result = await db.execute(query)
        bookings = result.scalars().all()

        return [booking_to_pydantic(b) for b in bookings]
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get("/{booking_id}", response_model=PydanticBooking)
async def get_booking(
        booking_id: int,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Получение информации о бронировании"""
    try:
        booking = await db.get(DBBooking, booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        if current_user.role != UserRole.ADMIN and booking.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own bookings"
            )

        return booking_to_pydantic(booking)
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )



@router.post("/", response_model=PydanticBooking, status_code=status.HTTP_201_CREATED)
async def create_new_booking(
        booking_data: BookingCreate,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    try:
        room = await db.get(DBMeetingRoom, booking_data.room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )
        if not room.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Room is not active"
            )
        time_slot = await db.get(DBTimeSlot, booking_data.time_slot_id)
        if not time_slot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time slot not found"
            )
        if time_slot.room_id != booking_data.room_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time slot does not belong to this room"
            )
        existing = await db.execute(
            select(DBBooking).where(
                DBBooking.room_id == booking_data.room_id,
                DBBooking.time_slot_id == booking_data.time_slot_id,
                DBBooking.booking_date == booking_data.booking_date,
                DBBooking.status != BookingStatus.CANCELLED
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Time slot is already booked on {booking_data.booking_date}"
            )

        if booking_data.booking_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book in the past"
            )

        new_booking = DBBooking(
            room_id=booking_data.room_id,
            time_slot_id=booking_data.time_slot_id,
            user_id=current_user.id,
            booking_date=booking_data.booking_date,
            title=booking_data.title or "Встреча",
            status=BookingStatus.ACTIVE
        )
        db.add(new_booking)
        await db.commit()
        await db.refresh(new_booking)

        return booking_to_pydantic(new_booking)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_booking(
        booking_id: int,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Отмена бронирования"""
    try:
        booking = await db.get(DBBooking, booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )


        is_admin = current_user.role == UserRole.ADMIN
        if not is_admin and booking.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only cancel your own bookings"
            )

        if booking.status == BookingStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking already cancelled"
            )

        await db.delete(booking)
        await db.commit()

        return None
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.post("/{booking_id}/cancel", response_model=PydanticBooking)
async def cancel_booking_post(
        booking_id: int,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Отмена бронирования (POST вариант)"""
    try:
        booking = await db.get(DBBooking, booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )

        is_admin = current_user.role == UserRole.ADMIN
        if not is_admin and booking.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only cancel your own bookings"
            )

        if booking.status == BookingStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking already cancelled"
            )

        await db.delete(booking)
        await db.commit()

        return booking_to_pydantic(booking)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
