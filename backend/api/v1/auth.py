"""
认证相关API
"""
import logging
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_db
from shared.models.user import User
from shared.schemas.user import (
    WechatLoginRequest,
    Token,
    UserResponse,
    UserQuota,
    UserLoginRequest,
)
from services.user_service import (
    authenticate_wechat_user,
    authenticate_preset_user,
    create_access_token,
    get_current_user,
    get_user_quota,
)
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_active_user(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> User:
    """
    获取当前认证用户，根据AUTH_MODE配置决定认证策略：
    - demo模式：返回模拟用户（忽略token）
    - jwt模式：要求有效的JWT token，否则抛出401异常
    """
    # demo模式：直接返回模拟用户
    if settings.AUTH_MODE == "demo":
        logger.info("demo模式：使用模拟用户")
        return await get_or_create_mock_user(db)

    # jwt模式：要求有效的JWT token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )
    return user


async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[User]:
    """
    获取当前用户（可选），根据AUTH_MODE配置决定认证策略：
    - demo模式：返回模拟用户
    - jwt模式：尝试认证，失败则返回None
    """
    # demo模式：直接返回模拟用户
    if settings.AUTH_MODE == "demo":
        logger.info("demo模式：使用模拟用户（可选认证）")
        return await get_or_create_mock_user(db)

    # jwt模式：尝试认证，失败则返回None
    try:
        user = await get_current_user(db, token)
        return user
    except HTTPException:
        return None


@router.post("/login", response_model=Token)
async def user_login(
    request: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    账号密码登录（预置用户）
    """
    try:
        user = await authenticate_preset_user(db, request.username, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        # 创建访问令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = await create_access_token(
            data={"sub": user.id, "is_admin": user.is_admin},
            expires_delta=access_token_expires,
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录失败",
        )


@router.post("/wechat/login", response_model=Token)
async def wechat_login(
    request: WechatLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    微信登录
    """
    try:
        user = await authenticate_wechat_user(db, request.code)

        # 创建访问令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = await create_access_token(
            data={"sub": user.id, "is_admin": user.is_admin},
            expires_delta=access_token_expires,
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception as e:
        logger.error(f"微信登录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="微信登录失败",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    获取当前用户信息
    """
    return UserResponse(
        **current_user.__dict__,
        is_banned=current_user.is_banned,
    )


@router.get("/quota", response_model=UserQuota)
async def get_user_quota_info(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    获取用户配额信息
    """
    return await get_user_quota(db, current_user.id)


@router.post("/refresh")
async def refresh_token(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    刷新访问令牌
    """
    # 创建新的访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = await create_access_token(
        data={"sub": current_user.id, "is_admin": current_user.is_admin},
        expires_delta=access_token_expires,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    用户登出
    """
    # 在实际实现中，可能需要将令牌加入黑名单
    # 这里简单返回成功
    return {"message": "登出成功"}


@router.get("/test")
async def test_auth(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    测试认证（开发用）
    """
    return {
        "message": "认证成功",
        "user_id": current_user.id,
        "nickname": current_user.nickname,
    }


# 辅助函数：获取或创建模拟用户
async def get_or_create_mock_user(db: AsyncSession) -> User:
    """
    获取或创建模拟用户
    """
    from sqlalchemy import select
    from datetime import datetime

    MOCK_USER_ID = "demo-user-001"

    try:
        # 尝试从数据库获取模拟用户
        result = await db.execute(select(User).where(User.id == MOCK_USER_ID))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            return existing_user

        # 创建模拟用户
        mock_user = User(
            id=MOCK_USER_ID,
            wechat_openid=f"mock-wechat-{MOCK_USER_ID}",
            nickname="模拟用户",
            avatar_url="https://example.com/avatar.jpg",
            is_active=True,
            is_premium=False,
            is_admin=False,
            daily_chat_count=0,
            daily_generate_count=0,
            total_chat_count=0,
            total_generate_count=0,
            preferred_voice="default",
            preferred_language="zh-CN",
            notification_enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(mock_user)
        await db.commit()
        await db.refresh(mock_user)
        return mock_user
    except Exception as e:
        logger.error(f"数据库操作失败，使用纯模拟用户: {e}")
        # 返回一个不依赖于数据库的模拟用户
        return User(
            id=MOCK_USER_ID,
            wechat_openid=f"mock-wechat-{MOCK_USER_ID}",
            nickname="模拟用户",
            avatar_url="https://example.com/avatar.jpg",
            is_active=True,
            is_premium=False,
            is_admin=False,
            daily_chat_count=0,
            daily_generate_count=0,
            total_chat_count=0,
            total_generate_count=0,
            preferred_voice="default",
            preferred_language="zh-CN",
            notification_enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )