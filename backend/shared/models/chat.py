"""
聊天数据模型
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Float, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship

from shared.database.session import Base


class ChatSession(Base):
    """
    聊天会话表
    """
    __tablename__ = "chat_sessions"

    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(200), nullable=True)  # 会话标题（可自动生成）
    is_active = Column(Boolean, default=True)  # 是否活跃

    # 上下文信息
    context_summary = Column(Text, nullable=True)  # 上下文摘要
    recent_topics = Column(JSON, nullable=True)  # 最近话题列表

    # 统计信息
    message_count = Column(Integer, default=0)  # 消息总数
    last_message_at = Column(DateTime, nullable=True)  # 最后消息时间

    # 偏好设置
    preferred_voice = Column(String(50), nullable=True)  # 偏好的语音
    preferred_topic = Column(String(100), nullable=True)  # 偏好的话题

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, user_id={self.user_id})>"

    def update_last_message_time(self) -> None:
        """更新最后消息时间"""
        self.last_message_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def increment_message_count(self) -> None:
        """增加消息计数"""
        self.message_count += 1
        self.updated_at = datetime.utcnow()


class ChatMessage(Base):
    """
    聊天消息表
    """
    __tablename__ = "chat_messages"

    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), index=True, nullable=False)
    audio_segment_id = Column(String(36), ForeignKey("audio_segments.id"), index=True, nullable=True)

    # 消息内容
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)  # 文本内容
    audio_url = Column(String(500), nullable=True)  # 音频URL（assistant消息）

    # 语义信息
    query_vector = Column(JSON, nullable=True)  # 用户查询向量
    similarity_score = Column(Float, nullable=True)  # 相似度分数

    # 情感分析
    emotion = Column(String(50), nullable=True)  # 情感标签
    sentiment_score = Column(Float, nullable=True)  # 情感分数

    # 用户反馈
    user_feedback = Column(String(20), nullable=True)  # like, dislike
    feedback_reason = Column(Text, nullable=True)  # 反馈原因

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    session = relationship("ChatSession", back_populates="messages")
    audio_segment = relationship("AudioSegment", back_populates="chat_messages")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role={self.role}, session_id={self.session_id})>"

    @property
    def is_user_message(self) -> bool:
        """是否是用户消息"""
        return self.role == "user"

    @property
    def is_assistant_message(self) -> bool:
        """是否是助手消息"""
        return self.role == "assistant"

    def set_feedback(self, feedback: str, reason: str = None) -> None:
        """设置用户反馈"""
        self.user_feedback = feedback
        self.feedback_reason = reason
        self.updated_at = datetime.utcnow()


class GeneratedAudio(Base):
    """
    生成的音频表
    """
    __tablename__ = "generated_audios"

    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    template_id = Column(String(50), nullable=False)  # 模板ID
    title = Column(String(200), nullable=False)  # 音频标题

    # 生成内容
    text_content = Column(Text, nullable=False)  # 生成的文本
    voice_type = Column(String(50), default="default")  # 语音类型
    background_music = Column(String(100), nullable=True)  # 背景音乐

    # 文件信息
    duration = Column(Float, nullable=False)  # 时长（秒）
    file_size = Column(Integer, nullable=False)  # 文件大小（字节）
    format = Column(String(20), default="mp3")  # 音频格式

    # 存储信息
    oss_key = Column(String(500), nullable=False)  # OSS存储键
    oss_url = Column(String(500), nullable=False)  # OSS访问URL
    share_code = Column(String(100), unique=True, index=True, nullable=False)  # 分享码

    # 使用统计
    play_count = Column(Integer, default=0)  # 播放次数
    share_count = Column(Integer, default=0)  # 分享次数
    download_count = Column(Integer, default=0)  # 下载次数

    # 审核状态
    review_status = Column(
        String(20),
        default="pending",  # pending, approved, rejected
        nullable=False
    )

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<GeneratedAudio(id={self.id}, title={self.title})>"

    @property
    def share_url(self) -> str:
        """分享URL"""
        return f"https://soundverse.example.com/share/{self.share_code}"

    def increment_play_count(self) -> None:
        """增加播放计数"""
        self.play_count += 1

    def increment_share_count(self) -> None:
        """增加分享计数"""
        self.share_count += 1

    def increment_download_count(self) -> None:
        """增加下载计数"""
        self.download_count += 1