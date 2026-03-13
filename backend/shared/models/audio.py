"""
音频数据模型
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Float, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import relationship

from shared.database.session import Base


class AudioSource(Base):
    """
    音频源表（整期节目）
    """
    __tablename__ = "audio_sources"

    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    program_type = Column(String(50), nullable=False)  # 节目类型：新闻、娱乐、教育等
    episode_number = Column(String(50), nullable=True)  # 期号
    broadcast_date = Column(DateTime, nullable=True)  # 播出日期

    # 文件信息
    original_filename = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # 文件大小（字节）
    duration = Column(Float, nullable=False)  # 时长（秒）
    format = Column(String(20), nullable=False)  # 音频格式：mp3, wav等
    sample_rate = Column(Integer, nullable=False)  # 采样率
    channels = Column(Integer, nullable=False)  # 声道数

    # 存储信息
    oss_key = Column(String(500), nullable=False)  # OSS存储键
    oss_url = Column(String(500), nullable=False)  # OSS访问URL

    # 处理状态
    processing_status = Column(
        String(20),
        default="pending",  # pending, processing, completed, failed
        nullable=False
    )
    processing_progress = Column(Float, default=0.0)  # 处理进度 0-1
    error_message = Column(Text, nullable=True)

    # 版权信息
    copyright_holder = Column(String(200), nullable=True)
    license_type = Column(String(50), nullable=True)
    is_public = Column(Boolean, default=True)  # 是否公开

    # 元数据
    tags = Column(JSON, nullable=True)  # 标签列表
    extra_metadata = Column(JSON, nullable=True)  # 额外元数据

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    segments = relationship("AudioSegment", back_populates="source", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AudioSource(id={self.id}, title={self.title})>"


class AudioSegment(Base):
    """
    音频片段表（分割后的句子/段落）
    """
    __tablename__ = "audio_segments"

    # 基础信息
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String(36), ForeignKey("audio_sources.id"), index=True, nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=True)  # 用户上传的片段

    # 位置信息
    start_time = Column(Float, nullable=False)  # 开始时间（秒）
    end_time = Column(Float, nullable=False)  # 结束时间（秒）
    duration = Column(Float, nullable=False)  # 时长（秒）

    # 内容信息
    transcription = Column(Text, nullable=True)  # 语音识别文本
    language = Column(String(10), default="zh-CN")  # 语言
    speaker = Column(String(100), nullable=True)  # 说话人
    emotion = Column(String(50), nullable=True)  # 情感：happy, sad, angry等
    sentiment_score = Column(Float, nullable=True)  # 情感分数 -1到1

    # 语义向量
    vector = Column(JSON, nullable=True)  # 语义向量（列表）
    vector_dimension = Column(Integer, nullable=True)  # 向量维度
    vector_updated_at = Column(DateTime, nullable=True)  # 向量更新时间

    # 存储信息
    oss_key = Column(String(500), nullable=False)  # OSS存储键
    oss_url = Column(String(500), nullable=False)  # OSS访问URL

    # 使用统计
    play_count = Column(Integer, default=0)  # 播放次数
    favorite_count = Column(Integer, default=0)  # 收藏次数
    share_count = Column(Integer, default=0)  # 分享次数

    # 标签和分类
    tags = Column(JSON, nullable=True)  # 标签列表
    categories = Column(JSON, nullable=True)  # 分类列表
    keywords = Column(JSON, nullable=True)  # 关键词列表

    # 审核状态
    review_status = Column(
        String(20),
        default="pending",  # pending, approved, rejected
        nullable=False
    )
    reviewer_id = Column(String(36), nullable=True)  # 审核人ID
    review_comment = Column(Text, nullable=True)  # 审核意见

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    source = relationship("AudioSource", back_populates="segments")
    user = relationship("User", back_populates="audio_segments")
    favorites = relationship("FavoriteSegment", back_populates="segment")
    chat_messages = relationship("ChatMessage", back_populates="audio_segment")

    def __repr__(self) -> str:
        return f"<AudioSegment(id={self.id}, source_id={self.source_id})>"

    @property
    def is_approved(self) -> bool:
        """片段是否已审核通过"""
        return self.review_status == "approved"

    def increment_play_count(self) -> None:
        """增加播放计数"""
        self.play_count += 1

    def increment_favorite_count(self) -> None:
        """增加收藏计数"""
        self.favorite_count += 1

    def increment_share_count(self) -> None:
        """增加分享计数"""
        self.share_count += 1


class FavoriteSegment(Base):
    """
    用户收藏的音频片段
    """
    __tablename__ = "favorite_segments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    segment_id = Column(String(36), ForeignKey("audio_segments.id"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="favorite_segments")
    segment = relationship("AudioSegment", back_populates="favorites")

    def __repr__(self) -> str:
        return f"<FavoriteSegment(user_id={self.user_id}, segment_id={self.segment_id})>"