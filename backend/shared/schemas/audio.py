"""
音频相关的Pydantic模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl


class AudioSourceBase(BaseModel):
    """音频源基础模型"""
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    program_type: str = Field(..., max_length=50)
    episode_number: Optional[str] = Field(None, max_length=50)
    broadcast_date: Optional[datetime] = None
    copyright_holder: Optional[str] = Field(None, max_length=200)
    license_type: Optional[str] = Field(None, max_length=50)
    is_public: bool = True
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class AudioSourceCreate(AudioSourceBase):
    """音频源创建模型"""
    original_filename: str = Field(..., max_length=500)
    file_size: int = Field(..., gt=0)
    duration: float = Field(..., gt=0)
    format: str = Field(..., max_length=20)
    sample_rate: int = Field(..., gt=0)
    channels: int = Field(..., ge=1, le=2)


class AudioSourceUpdate(BaseModel):
    """音频源更新模型"""
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    program_type: Optional[str] = Field(None, max_length=50)
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None


class AudioSourceInDB(AudioSourceBase):
    """数据库中的音频源模型"""
    id: str
    original_filename: str
    file_size: int
    duration: float
    format: str
    sample_rate: int
    channels: int
    oss_key: str
    oss_url: str
    processing_status: str
    processing_progress: float
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AudioSourceResponse(AudioSourceInDB):
    """音频源响应模型"""
    segments_count: int = 0


class AudioSegmentBase(BaseModel):
    """音频片段基础模型"""
    source_id: str
    start_time: float = Field(..., ge=0)
    end_time: float = Field(..., gt=0)
    duration: float = Field(..., gt=0)
    transcription: Optional[str] = None
    language: str = "zh-CN"
    speaker: Optional[str] = Field(None, max_length=100)
    emotion: Optional[str] = Field(None, max_length=50)
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    keywords: Optional[List[str]] = None


class AudioSegmentCreate(AudioSegmentBase):
    """音频片段创建模型"""
    oss_key: str
    oss_url: str


class AudioSegmentUpdate(BaseModel):
    """音频片段更新模型"""
    transcription: Optional[str] = None
    speaker: Optional[str] = None
    emotion: Optional[str] = None
    sentiment_score: Optional[float] = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    review_status: Optional[str] = None
    review_comment: Optional[str] = None


class AudioSegmentInDB(AudioSegmentBase):
    """数据库中的音频片段模型"""
    id: str
    user_id: Optional[str] = None
    vector: Optional[List[float]] = None
    vector_dimension: Optional[int] = None
    vector_updated_at: Optional[datetime] = None
    oss_key: str
    oss_url: str
    play_count: int = 0
    favorite_count: int = 0
    share_count: int = 0
    review_status: str = "pending"
    reviewer_id: Optional[str] = None
    review_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AudioSegmentResponse(AudioSegmentInDB):
    """音频片段响应模型"""
    is_favorite: bool = False
    source_title: Optional[str] = None


class AudioUploadRequest(BaseModel):
    """音频上传请求模型"""
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    program_type: str = Field(..., max_length=50)
    tags: Optional[List[str]] = None
    is_public: bool = True


class AudioUploadResponse(BaseModel):
    """音频上传响应模型"""
    upload_id: str
    oss_policy: Dict[str, Any]
    oss_signature: str
    oss_key: str
    oss_host: str
    callback_url: str


class AudioProcessingStatus(BaseModel):
    """音频处理状态响应"""
    processing_id: str
    status: str  # pending, processing, completed, failed
    progress: float = 0.0  # 0-1
    estimated_time_remaining: Optional[float] = None  # 秒
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class AudioSearchRequest(BaseModel):
    """音频搜索请求模型"""
    query: str = Field(..., min_length=1, max_length=500)
    program_types: Optional[List[str]] = None
    min_duration: Optional[float] = Field(None, ge=0)
    max_duration: Optional[float] = Field(None, gt=0)
    language: Optional[str] = "zh-CN"
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)


class AudioSearchResult(BaseModel):
    """音频搜索结果"""
    segment: AudioSegmentResponse
    similarity_score: float = Field(..., ge=0, le=1)
    relevance_explanation: Optional[str] = None


class AudioSearchResponse(BaseModel):
    """音频搜索响应"""
    query: str
    results: List[AudioSearchResult]
    total_count: int
    processing_time_ms: float


class AudioBatchProcessRequest(BaseModel):
    """音频批量处理请求"""
    source_ids: List[str] = Field(..., min_items=1)
    process_types: List[str] = Field(["transcribe", "vectorize"], min_items=1)
    force_reprocess: bool = False


class FavoriteSegmentCreate(BaseModel):
    """收藏音频片段请求"""
    segment_id: str


class FavoriteSegmentResponse(BaseModel):
    """收藏音频片段响应"""
    id: str
    user_id: str
    segment: AudioSegmentResponse
    created_at: datetime