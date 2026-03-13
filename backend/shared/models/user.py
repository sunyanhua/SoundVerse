"""
用户数据模型
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Float
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.orm import relationship

from shared.database.session import Base


class User(Base):
    """
    用户表
    """
    __tablename__ = "users"

    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wechat_openid = Column(String(128), unique=True, index=True, nullable=True)
    wechat_unionid = Column(String(128), unique=True, index=True, nullable=True)
    nickname = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    gender = Column(Integer, default=0)  # 0: 未知, 1: 男性, 2: 女性
    country = Column(String(50), nullable=True)
    province = Column(String(50), nullable=True)
    city = Column(String(50), nullable=True)

    # 账户状态
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    banned_until = Column(DateTime, nullable=True)

    # 使用统计
    daily_chat_count = Column(Integer, default=0)
    daily_generate_count = Column(Integer, default=0)
    total_chat_count = Column(Integer, default=0)
    total_generate_count = Column(Integer, default=0)
    last_active_at = Column(DateTime, nullable=True)

    # 偏好设置
    preferred_voice = Column(String(50), default="default")
    preferred_language = Column(String(10), default="zh-CN")
    notification_enabled = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    audio_segments = relationship("AudioSegment", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")
    favorite_segments = relationship("FavoriteSegment", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, nickname={self.nickname})>"

    @property
    def is_banned(self) -> bool:
        """用户是否被封禁"""
        if self.banned_until:
            return self.banned_until > datetime.utcnow()
        return False

    def increment_chat_count(self) -> None:
        """增加聊天计数"""
        self.daily_chat_count += 1
        self.total_chat_count += 1
        self.last_active_at = datetime.utcnow()

    def increment_generate_count(self) -> None:
        """增加生成计数"""
        self.daily_generate_count += 1
        self.total_generate_count += 1
        self.last_active_at = datetime.utcnow()

    def reset_daily_counts(self) -> None:
        """重置每日计数"""
        self.daily_chat_count = 0
        self.daily_generate_count = 0


class UserToken(Base):
    """
    用户令牌表
    """
    __tablename__ = "user_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)
    token = Column(String(512), unique=True, index=True, nullable=False)
    token_type = Column(String(50), default="access")  # access, refresh
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UserToken(user_id={self.user_id}, token_type={self.token_type})>"

    @property
    def is_expired(self) -> bool:
        """令牌是否过期"""
        return self.expires_at < datetime.utcnow()


class UserUsage(Base):
    """
    用户使用量统计表
    """
    __tablename__ = "user_usage"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True, nullable=False)
    date = Column(DateTime, index=True, nullable=False)  # 统计日期
    asr_seconds = Column(Float, default=0.0)  # ASR识别秒数
    tts_chars = Column(Integer, default=0)  # TTS合成字符数
    nlp_requests = Column(Integer, default=0)  # NLP请求次数
    audio_storage_mb = Column(Float, default=0.0)  # 音频存储MB
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UserUsage(user_id={self.user_id}, date={self.date})>"