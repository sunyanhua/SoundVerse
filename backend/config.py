"""
应用配置管理
"""
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用设置
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",  # 允许额外的环境变量
    )

    # 应用基础配置
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 安全配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    # CORS 配置
    CORS_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # 数据库配置
    DATABASE_URL: str = "mysql+asyncmy://user:password@localhost:3306/soundverse"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_ECHO: bool = False

    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 10

    # 阿里云配置
    ALIYUN_ACCESS_KEY_ID: Optional[str] = None
    ALIYUN_ACCESS_KEY_SECRET: Optional[str] = None
    ALIYUN_REGION_ID: str = "cn-hangzhou"
    ALIYUN_OSS_BUCKET_NAME: Optional[str] = None  # 兼容旧配置
    ALIYUN_OSS_ENDPOINT: Optional[str] = None  # 兼容旧配置

    # 阿里云智能语音交互 (ASR/TTS)
    ALIYUN_ASR_APP_KEY: Optional[str] = None
    ALIYUN_TTS_APP_KEY: Optional[str] = None

    # 阿里云自然语言处理 (NLP)
    ALIYUN_NLP_ACCESS_KEY_ID: Optional[str] = None
    ALIYUN_NLP_ACCESS_KEY_SECRET: Optional[str] = None

    # 百炼平台 (兼容旧配置)
    BAILIAN_API_KEY: Optional[str] = None

    # 对象存储 OSS 配置
    OSS_ENDPOINT: str = "oss-cn-beijing.aliyuncs.com"
    OSS_BUCKET: str = "ai-sun-vbegin-com-cn"
    OSS_PREFIX: str = "audio/"
    OSS_PUBLIC_DOMAIN: str = "https://ai-sun.vbegin.com.cn"  # 公开访问的自定义域名

    # 百炼平台 (DashScope/Bailian) 配置
    DASHSCOPE_API_KEY: Optional[str] = None
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v4"
    DASHSCOPE_WORKSPACE_ID: Optional[str] = None

    # DashVector 向量检索服务配置
    DASHVECTOR_ENDPOINT: Optional[str] = None
    DASHVECTOR_API_KEY: Optional[str] = None
    DASHVECTOR_NAMESPACE: str = "soundverse"
    DASHVECTOR_COLLECTION: str = "audio_segments"
    DASHVECTOR_COLLECTION_DIMENSION: int = 1024  # text-embedding-v3 维度

    # 文件存储配置
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_AUDIO_TYPES: List[str] = ["mp3", "wav", "m4a", "ogg", "flac"]

    # 音频处理配置
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1
    AUDIO_BITRATE: str = "64k"
    MIN_AUDIO_DURATION: float = 1.0  # 最短音频时长（秒）
    MAX_AUDIO_DURATION: float = 300.0  # 最长音频时长（秒）

    # 音频分割配置
    MIN_SILENCE_LEN: int = 300  # 毫秒（降低以检测更短的静音）
    SILENCE_THRESH: int = -35  # dB（稍微提高阈值，检测更敏感的静音）
    KEEP_SILENCE: int = 100  # 毫秒（减少保留的静音）
    MIN_SEGMENT_DURATION: float = 1.5  # 最短片段时长（秒）
    MAX_SEGMENT_DURATION: float = 8.0  # 最长片段时长（秒）大幅缩短至8秒，切出"短小精干、语义集中"的短句

    # 语义搜索配置
    VECTOR_DIMENSION: int = 1024  # text-embedding-v4 维度
    FAISS_INDEX_PATH: str = "data/faiss_index.bin"  # 保留兼容性，将逐步迁移到DashVector
    SEARCH_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.25  # 进一步降低阈值，匹配0.2-0.4的相似度范围

    # 聊天回复配置
    AUDIO_REPLY_THRESHOLD: float = 0.25  # 直接播放门槛，降低至0.25
    AUDIO_SUGGEST_THRESHOLD: float = 0.15  # 引导播放门槛，新增

    # 缓存配置
    CACHE_TTL: int = 3600  # 1小时
    USER_CACHE_TTL: int = 1800  # 30分钟
    AUDIO_CACHE_TTL: int = 86400  # 24小时

    # 速率限制
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # 微信小程序配置
    WECHAT_APP_ID: Optional[str] = None
    WECHAT_APP_SECRET: Optional[str] = None

    # 监控配置
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/soundverse.log"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Celery 配置
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    @property
    def is_production(self) -> bool:
        """是否生产环境"""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """是否开发环境"""
        return self.ENVIRONMENT == "development"

    @property
    def is_testing(self) -> bool:
        """是否测试环境"""
        return self.ENVIRONMENT == "testing"

    def get_database_url(self) -> str:
        """获取数据库连接URL（可在此处添加额外处理）"""
        return self.DATABASE_URL

    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        return self.REDIS_URL


# 创建全局设置实例
settings = Settings()