# routers/auth.py
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from models import UserLogin, Token, User as PydanticUser
from db_models import User as DBUser
from auth import create_access_token, verify_password
from database import get_db
from dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
        login_data: UserLogin,
        db: AsyncSession = Depends(get_db)
):
    """
    Вход в систему
    """
    try:

        result = await db.execute(
            select(DBUser).where(DBUser.email == login_data.email)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )


        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )


        access_token = create_access_token({
            "user_id": user.id,
            "username": user.username,
            "role": user.role
        })


        response = JSONResponse(content={
            "message": "Login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role
            }
        })

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=1800,
            secure=True,
            samesite="lax",
            path="/"
        )

        return response

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.post("/logout")
async def logout():
    """
    Выход из системы (очистка cookie)
    """
    response = JSONResponse(content={"message": "Logout successful"})
    response.delete_cookie("access_token", path="/")
    return response


@router.get("/me", response_model=PydanticUser)
async def get_current_user_info(
        current_user: PydanticUser = Depends(get_current_user)
):
    """
    Получение информации о текущем пользователе
    """
    return current_user


@router.post("/refresh", response_model=Token)
async def refresh_token(
        current_user: PydanticUser = Depends(get_current_user)
):
    """
    Обновление JWT токена
    """
    access_token = create_access_token({
        "user_id": current_user.id,
        "username": current_user.username,
        "role": current_user.role
    })

    return Token(access_token=access_token, token_type="bearer")


@router.post("/register")
async def register(
        register_data: dict,
        db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя
    """
    from database import hash_password

    try:

        result = await db.execute(
            select(DBUser).where(DBUser.email == register_data.get("email"))
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )


        result = await db.execute(
            select(DBUser).where(DBUser.username == register_data.get("username"))
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )


        new_user = DBUser(
            email=register_data.get("email"),
            username=register_data.get("username"),
            full_name=register_data.get("full_name"),
            hashed_password=hash_password(register_data.get("password")),
            role=register_data.get("role", "employee"),
            is_active=True
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)


        access_token = create_access_token({
            "user_id": new_user.id,
            "username": new_user.username,
            "role": new_user.role
        })

        response = JSONResponse(content={
            "message": "Registration successful",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "role": new_user.role
            }
        })

        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            max_age=1800,
            secure=True,
            samesite="lax",
            path="/"
        )

        return response

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get("/check")
async def check_auth(
        request: Request,
        db: AsyncSession = Depends(get_db)
):
    """
    Проверка авторизации (проверка токена в cookies)
    """
    token = request.cookies.get("access_token")

    if not token:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"authenticated": False, "message": "No token found"}
        )

    try:
        from auth import decode_token
        payload = decode_token(token)
        user_id = payload.get("user_id")

        user = await db.get(DBUser, user_id)
        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"authenticated": False, "message": "User not found"}
            )

        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role
            }
        }
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"authenticated": False, "message": "Invalid token"}
        )