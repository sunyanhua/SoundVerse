"""
聊天相关的Pydantic模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatSessionBase(BaseModel):
    """聊天会话基础模型"""
    title: Optional[str] = Field(None, max_length=200)
    preferred_voice: Optional[str] = None
    preferred_topic: Optional[str] = None


class ChatSessionCreate(ChatSessionBase):
    """聊天会话创建模型"""
    pass


class ChatSessionUpdate(ChatSessionBase):
    """聊天会话更新模型"""
    is_active: Optional[bool] = None


class ChatSessionInDB(ChatSessionBase):
    """数据库中的聊天会话模型"""
    id: str
    user_id: str
    is_active: bool = True
    context_summary: Optional[str] = None
    recent_topics: Optional[List[str]] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionResponse(ChatSessionInDB):
    """聊天会话响应模型"""
    unread_count: int = 0
    last_message_preview: Optional[str] = None


class ChatMessageBase(BaseModel):
    """聊天消息基础模型"""
    content: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None  # 如果为空，创建新会话


class ChatMessageCreate(ChatMessageBase):
    """聊天消息创建模型"""
    pass


class ChatMessageUpdate(BaseModel):
    """聊天消息更新模型"""
    user_feedback: Optional[str] = Field(None, pattern="^(like|dislike)$")
    feedback_reason: Optional[str] = None


class ChatMessageInDB(BaseModel):
    """数据库中的聊天消息模型"""
    id: str
    session_id: str
    audio_segment_id: Optional[str] = None
    role: str  # user, assistant
    content: str
    audio_url: Optional[str] = None
    query_vector: Optional[List[float]] = None
    similarity_score: Optional[float] = None
    emotion: Optional[str] = None
    sentiment_score: Optional[float] = None
    user_feedback: Optional[str] = None
    feedback_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatMessageResponse(ChatMessageInDB):
    """聊天消息响应模型"""
    audio_segment_preview: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """聊天响应模型"""
    message: ChatMessageResponse
    session: Optional[ChatSessionResponse] = None
    suggestions: Optional[List[str]] = None  # 建议的回复


class ChatHistoryRequest(BaseModel):
    """聊天历史请求"""
    session_id: Optional[str] = None
    limit: int = Field(50, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ChatHistoryResponse(BaseModel):
    """聊天历史响应"""
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]
    has_more: bool


class GeneratedAudioBase(BaseModel):
    """生成的音频基础模型"""
    template_id: str = Field(..., max_length=50)
    title: str = Field(..., max_length=200)
    text_content: str = Field(..., min_length=1, max_length=1000)
    voice_type: str = "default"
    background_music: Optional[str] = None


class GeneratedAudioCreate(GeneratedAudioBase):
    """生成的音频创建模型"""
    pass


class GeneratedAudioUpdate(BaseModel):
    """生成的音频更新模型"""
    title: Optional[str] = None
    review_status: Optional[str] = None


class GeneratedAudioInDB(GeneratedAudioBase):
    """数据库中的生成音频模型"""
    id: str
    user_id: str
    duration: float
    file_size: int
    format: str = "mp3"
    oss_key: str
    oss_url: str
    share_code: str
    play_count: int = 0
    share_count: int = 0
    download_count: int = 0
    review_status: str = "pending"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GeneratedAudioResponse(GeneratedAudioInDB):
    """生成的音频响应模型"""
    share_url: str


class AudioTemplate(BaseModel):
    """音频模板"""
    id: str
    name: str
    description: str
    category: str  # 祝福、表白、道歉、整蛊等
    example_text: str
    variable_fields: List[Dict[str, Any]]  # 变量字段定义
    background_music_options: List[str]
    voice_options: List[str]
    estimated_duration: float  # 估计时长（秒）


class TemplateCategory(BaseModel):
    """模板分类"""
    id: str
    name: str
    description: str
    icon: str
    templates: List[AudioTemplate]


class GenerateAudioRequest(BaseModel):
    """生成音频请求"""
    template_id: str
    variables: Dict[str, str] = Field(default_factory=dict)
    voice_type: Optional[str] = "default"
    background_music: Optional[str] = None


class GenerateAudioResponse(BaseModel):
    """生成音频响应"""
    audio: GeneratedAudioResponse
    estimated_wait_time: Optional[float] = None  # 估计等待时间（秒）


class ShareAudioRequest(BaseModel):
    """分享音频请求"""
    audio_id: str
    share_to: Optional[str] = None  # wechat, wechat_moments, qq等
    message: Optional[str] = None


class ShareAudioResponse(BaseModel):
    """分享音频响应"""
    share_url: str
    qr_code_url: Optional[str] = None
    short_url: Optional[str] = None