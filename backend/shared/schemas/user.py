"""
用户相关的Pydantic模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class UserBase(BaseModel):
    """用户基础模型"""
    nickname: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    gender: Optional[int] = Field(None, ge=0, le=2)  # 0: 未知, 1: 男性, 2: 女性
    country: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None


class UserCreate(UserBase):
    """用户创建模型"""
    wechat_openid: str = Field(..., max_length=128)
    wechat_unionid: Optional[str] = Field(None, max_length=128)


class UserUpdate(UserBase):
    """用户更新模型"""
    preferred_voice: Optional[str] = None
    preferred_language: Optional[str] = None
    notification_enabled: Optional[bool] = None


class UserInDB(UserBase):
    """数据库中的用户模型"""
    id: str
    wechat_openid: Optional[str] = None
    wechat_unionid: Optional[str] = None
    is_active: bool
    is_premium: bool
    is_admin: bool
    daily_chat_count: int
    daily_generate_count: int
    total_chat_count: int
    total_generate_count: int
    last_active_at: Optional[datetime] = None
    preferred_voice: str = "default"
    preferred_language: str = "zh-CN"
    notification_enabled: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(UserInDB):
    """用户响应模型"""
    is_banned: bool = False


class Token(BaseModel):
    """令牌响应模型"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    """令牌数据模型"""
    user_id: Optional[str] = None
    is_admin: bool = False


class WechatLoginRequest(BaseModel):
    """微信登录请求模型"""
    code: str = Field(..., description="微信登录code")


class WechatUserInfo(BaseModel):
    """微信用户信息模型"""
    openId: str
    nickName: str
    gender: int
    city: str
    province: str
    country: str
    avatarUrl: str
    unionId: Optional[str] = None


class UserStats(BaseModel):
    """用户统计信息"""
    user_id: str
    date: datetime
    asr_seconds: float = 0.0
    tts_chars: int = 0
    nlp_requests: int = 0
    audio_storage_mb: float = 0.0


class UserQuota(BaseModel):
    """用户配额信息"""
    daily_chat_limit: int = 50
    daily_generate_limit: int = 10
    daily_asr_limit: float = 300.0  # 秒
    daily_tts_limit: int = 5000  # 字符
    daily_nlp_limit: int = 100  # 请求次数

    used_chat_count: int = 0
    used_generate_count: int = 0
    used_asr_seconds: float = 0.0
    used_tts_chars: int = 0
    used_nlp_requests: int = 0

    @property
    def remaining_chat_count(self) -> int:
        return max(0, self.daily_chat_limit - self.used_chat_count)

    @property
    def remaining_generate_count(self) -> int:
        return max(0, self.daily_generate_limit - self.used_generate_count)

    @property
    def remaining_asr_seconds(self) -> float:
        return max(0.0, self.daily_asr_limit - self.used_asr_seconds)

    @property
    def remaining_tts_chars(self) -> int:
        return max(0, self.daily_tts_limit - self.used_tts_chars)

    @property
    def remaining_nlp_requests(self) -> int:
        return max(0, self.daily_nlp_limit - self.used_nlp_requests)