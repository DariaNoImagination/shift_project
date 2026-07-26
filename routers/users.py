from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models import User as PydanticUser
from db_models import User as DBUser
from database import get_db
from dependencies import get_current_user
from auth import get_password_hash

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[PydanticUser])
async def get_users(
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        result = await db.execute(select(DBUser))
        users = result.scalars().all()


        return [
            PydanticUser(
                id=user.id,
                email=user.email,
                username=user.username,
                full_name=user.full_name,
                hashed_password=user.hashed_password,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
            for user in users
        ]
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get("/me", response_model=PydanticUser)
async def get_current_user_info(
        current_user: PydanticUser = Depends(get_current_user)
):

    return current_user


@router.get("/{user_id}", response_model=PydanticUser)
async def get_user(
        user_id: int,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,

        )

    try:
        user = await db.get(DBUser, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )


        return PydanticUser(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            hashed_password=user.hashed_password,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.put("/me", response_model=PydanticUser)
async def update_current_user(
        user_data: dict,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    try:
        user = await db.get(DBUser, current_user.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )


        if "full_name" in user_data:
            user.full_name = user_data["full_name"]
        if "username" in user_data:

            existing = await db.execute(
                select(DBUser).where(
                    DBUser.username == user_data["username"],
                    DBUser.id != current_user.id
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            user.username = user_data["username"]
        if "email" in user_data:
            # Проверка уникальности email
            existing = await db.execute(
                select(DBUser).where(
                    DBUser.email == user_data["email"],
                    DBUser.id != current_user.id
                )
            )
            if existing.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            user.email = user_data["email"]
        if "password" in user_data:
            user.hashed_password = get_password_hash(user_data["password"])

        await db.commit()
        await db.refresh(user)

        return PydanticUser(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            hashed_password=user.hashed_password,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):

    try:
        user = await db.get(DBUser, current_user.id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )


        user.is_active = False
        await db.commit()
        return None
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
        user_id: int,
        current_user: PydanticUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):


    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            
        )

    try:
        user = await db.get(DBUser, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )


        user.is_active = False
        await db.commit()
        return None
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )