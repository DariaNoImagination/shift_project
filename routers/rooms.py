from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from models import MeetingRoom as PydanticMeetingRoom, RoomAvailability, TimeSlot as PydanticTimeSlot, \
    Booking as PydanticBooking, User as PydanticUser
from db_models import MeetingRoom as DBMeetingRoom, TimeSlot as DBTimeSlot, Booking as DBBooking
from database import get_db
from dependencies import get_current_user
from models import UserRole

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("/", response_model=List[PydanticMeetingRoom])
async def get_rooms(
        is_active: Optional[bool] = Query(None, description="Фильтр по активности"),
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    try:
        query = select(DBMeetingRoom)
        if is_active is not None:
            query = query.where(DBMeetingRoom.is_active == is_active)

        result = await db.execute(query)
        rooms = result.scalars().all()


        return [
            PydanticMeetingRoom(
                id=room.id,
                name=room.name,
                description=room.description,
                capacity=room.capacity,
                location=room.location,
                is_active=room.is_active,
                created_at=room.created_at,
                time_slots=[]
            )
            for room in rooms
        ]
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.post("/", response_model=PydanticMeetingRoom, status_code=status.HTTP_201_CREATED)
async def create_room(
        room_data: dict,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):


    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:

        existing = await db.execute(
            select(DBMeetingRoom).where(DBMeetingRoom.name == room_data.get("name"))
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Room with this name already exists"
            )


        new_room = DBMeetingRoom(
            name=room_data.get("name"),
            description=room_data.get("description"),
            capacity=room_data.get("capacity", 1),
            location=room_data.get("location"),
            is_active=room_data.get("is_active", True)
        )
        db.add(new_room)
        await db.commit()
        await db.refresh(new_room)


        default_slots = [
            ("09:00", "11:00"),
            ("11:00", "13:00"),
            ("13:00", "15:00"),
            ("15:00", "17:00"),
            ("17:00", "19:00"),
        ]

        for start, end in default_slots:
            slot = DBTimeSlot(
                room_id=new_room.id,
                start_time=datetime.strptime(start, "%H:%M").time(),
                end_time=datetime.strptime(end, "%H:%M").time(),
                is_available=True
            )
            db.add(slot)

        await db.commit()
        await db.refresh(new_room)

        return PydanticMeetingRoom(
            id=new_room.id,
            name=new_room.name,
            description=new_room.description,
            capacity=new_room.capacity,
            location=new_room.location,
            is_active=new_room.is_active,
            created_at=new_room.created_at,
            time_slots=[]
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Room with this name already exists"
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.put("/{room_id}", response_model=PydanticMeetingRoom)
async def update_room(
        room_id: int,
        room_data: dict,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        room = await db.get(DBMeetingRoom, room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )


        if "name" in room_data:

            existing = await db.execute(
                select(DBMeetingRoom).where(
                    DBMeetingRoom.name == room_data["name"],
                    DBMeetingRoom.id != room_id
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Room with this name already exists"
                )
            room.name = room_data["name"]
        if "description" in room_data:
            room.description = room_data["description"]
        if "capacity" in room_data:
            room.capacity = room_data["capacity"]
        if "location" in room_data:
            room.location = room_data["location"]
        if "is_active" in room_data:
            room.is_active = room_data["is_active"]

        await db.commit()
        await db.refresh(room)

        return PydanticMeetingRoom(
            id=room.id,
            name=room.name,
            description=room.description,
            capacity=room.capacity,
            location=room.location,
            is_active=room.is_active,
            created_at=room.created_at,
            time_slots=[]
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
        room_id: int,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        room = await db.get(DBMeetingRoom, room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )


        room.is_active = False
        await db.commit()
        return None
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.post("/{room_id}/slots", status_code=status.HTTP_201_CREATED)
async def add_time_slot(
        room_id: int,
        slot_data: dict,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):


    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        room = await db.get(DBMeetingRoom, room_id)
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )


        existing = await db.execute(
            select(DBTimeSlot).where(
                DBTimeSlot.room_id == room_id,
                DBTimeSlot.start_time == slot_data.get("start_time"),
                DBTimeSlot.end_time == slot_data.get("end_time")
            )
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time slot already exists for this room"
            )

        new_slot = DBTimeSlot(
            room_id=room_id,
            start_time=slot_data.get("start_time"),
            end_time=slot_data.get("end_time"),
            is_available=slot_data.get("is_available", True)
        )
        db.add(new_slot)
        await db.commit()
        await db.refresh(new_slot)

        return {
            "id": new_slot.id,
            "room_id": new_slot.room_id,
            "start_time": new_slot.start_time.isoformat(),
            "end_time": new_slot.end_time.isoformat(),
            "is_available": new_slot.is_available,
            "message": "Time slot created successfully"
        }
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )