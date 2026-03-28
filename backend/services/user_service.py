"""
用户服务
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import httpx
from jose import JWTError, jwt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from shared.models.user import User, UserToken, UserUsage
from shared.schemas.user import UserQuota, WechatUserInfo

logger = logging.getLogger(__name__)


async def authenticate_wechat_user(
    db: AsyncSession,
    code: str,
) -> User:
    """
    微信用户认证
    """
    # 调用微信API获取openid
    wechat_user_info = await get_wechat_user_info(code)

    # 查找或创建用户
    user = await get_or_create_user_by_wechat(db, wechat_user_info)

    return user


async def get_wechat_user_info(code: str) -> WechatUserInfo:
    """
    通过code获取微信用户信息
    """
    # 这里应该调用微信API，由于是示例，模拟返回
    # 实际实现需要调用微信API: https://api.weixin.qq.com/sns/jscode2session

    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        logger.warning("微信小程序配置未设置，使用模拟数据")
        # 模拟返回
        mock_openid = f"mock_openid_{code[:8]}"
        return WechatUserInfo(
            openId=mock_openid,
            nickName=f"测试用户{mock_openid[-6:]}",
            gender=0,
            city="",
            province="",
            country="",
            avatarUrl="https://mmbiz.qpic.cn/mmbiz/icTdbqWNOwNRna42FI242Lcia07jQodd2FJGIYQfG0LAJGFxM4FbnQP6yfMxBgJ0F3YRqJCJ1aPAK2dQagdusBZg/0",
        )

    try:
        async with httpx.AsyncClient() as client:
            # 获取session_key和openid
            session_response = await client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": settings.WECHAT_APP_ID,
                    "secret": settings.WECHAT_APP_SECRET,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
                timeout=10.0,
            )

            if session_response.status_code != 200:
                raise ValueError(f"微信API调用失败: {session_response.text}")

            session_data = session_response.json()

            if "errcode" in session_data and session_data["errcode"] != 0:
                raise ValueError(f"微信API返回错误: {session_data}")

            openid = session_data.get("openid")
            session_key = session_data.get("session_key")
            unionid = session_data.get("unionid")

            # 在实际应用中，这里可能需要进一步获取用户详细信息
            # 由于微信小程序前端已经获取了用户信息，可以直接使用

            return WechatUserInfo(
                openId=openid,
                nickName=f"用户{openid[-6:]}" if openid else "微信用户",  # 使用openid后6位作为默认昵称
                gender=0,
                city="",
                province="",
                country="",
                avatarUrl="https://mmbiz.qpic.cn/mmbiz/icTdbqWNOwNRna42FI242Lcia07jQodd2FJGIYQfG0LAJGFxM4FbnQP6yfMxBgJ0F3YRqJCJ1aPAK2dQagdusBZg/0",  # 微信默认头像
                unionId=unionid,
            )

    except Exception as e:
        logger.error(f"获取微信用户信息失败: {str(e)}")
        raise


async def get_or_create_user_by_wechat(
    db: AsyncSession,
    wechat_info: WechatUserInfo,
) -> User:
    """
    根据微信信息获取或创建用户
    """
    # 查找用户
    stmt = select(User).where(
        User.wechat_openid == wechat_info.openId
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # 更新最后活跃时间
        user.last_active_at = datetime.utcnow()
        await db.commit()
        return user

    # 创建新用户
    user = User(
        wechat_openid=wechat_info.openId,
        wechat_unionid=wechat_info.unionId,
        nickname=wechat_info.nickName,
        avatar_url=wechat_info.avatarUrl,
        gender=wechat_info.gender,
        country=wechat_info.country,
        province=wechat_info.province,
        city=wechat_info.city,
        last_active_at=datetime.utcnow(),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(f"创建新用户: {user.id}")
    return user


async def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建访问令牌
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt


async def verify_token(token: str) -> Dict[str, Any]:
    """
    验证令牌
    """
    # 防止传入非字符串对象（如Depends对象）
    if not isinstance(token, str):
        raise ValueError(f"Token must be a string, got {type(token).__name__}")

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError:
        return None


async def get_current_user(
    db: AsyncSession,
    token: str,
) -> Optional[User]:
    """
    获取当前用户
    """
    payload = await verify_token(token)
    if payload is None:
        return None

    user_id: str = payload.get("sub")
    if user_id is None:
        return None

    # 简化：跳过令牌黑名单检查，仅验证JWT有效性

    # 获取用户
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # 更新最后活跃时间
        user.last_active_at = datetime.utcnow()
        await db.commit()

    return user


async def get_user_quota(db: AsyncSession, user_id: str) -> UserQuota:
    """
    获取用户配额信息
    """
    # 获取今日使用量
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())

    stmt = select(
        func.sum(UserUsage.asr_seconds).label("asr_seconds"),
        func.sum(UserUsage.tts_chars).label("tts_chars"),
        func.sum(UserUsage.nlp_requests).label("nlp_requests"),
    ).where(
        UserUsage.user_id == user_id,
        UserUsage.date >= today_start,
    )

    result = await db.execute(stmt)
    usage = result.first()

    # 获取用户
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError(f"用户不存在: {user_id}")

    return UserQuota(
        daily_chat_limit=50,
        daily_generate_limit=10,
        daily_asr_limit=300.0,
        daily_tts_limit=5000,
        daily_nlp_limit=100,
        used_chat_count=user.daily_chat_count,
        used_generate_count=user.daily_generate_count,
        used_asr_seconds=usage.asr_seconds or 0.0,
        used_tts_chars=usage.tts_chars or 0,
        used_nlp_requests=usage.nlp_requests or 0,
    )


async def record_user_usage(
    db: AsyncSession,
    user_id: str,
    usage_type: str,
    amount: float,
) -> None:
    """
    记录用户使用量
    """
    today = datetime.utcnow().date()

    # 查找今日记录
    stmt = select(UserUsage).where(
        UserUsage.user_id == user_id,
        UserUsage.date >= today,
    )
    result = await db.execute(stmt)
    user_usage = result.scalar_one_or_none()

    if not user_usage:
        user_usage = UserUsage(
            user_id=user_id,
            date=datetime.utcnow(),
        )
        db.add(user_usage)

    # 更新使用量
    if usage_type == "asr":
        user_usage.asr_seconds += amount
    elif usage_type == "tts":
        user_usage.tts_chars += int(amount)
    elif usage_type == "nlp":
        user_usage.nlp_requests += int(amount)
    elif usage_type == "storage":
        user_usage.audio_storage_mb += amount

    await db.commit()


async def reset_daily_counts(db: AsyncSession) -> None:
    """
    重置每日计数（应在每天凌晨调用）
    """
    stmt = select(User)
    result = await db.execute(stmt)
    users = result.scalars().all()

    for user in users:
        user.reset_daily_counts()

    await db.commit()