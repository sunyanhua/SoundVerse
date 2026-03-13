"""
存储服务 - OSS对象存储集成
"""
import logging
import uuid
import oss2
from pathlib import Path
from typing import Optional, Tuple, BinaryIO
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    存储服务类 - 处理OSS上传和文件管理
    """

    def __init__(self):
        self.initialized = False
        self.oss_client = None
        self.oss_bucket = None
        self.access_key_id = settings.ALIYUN_ACCESS_KEY_ID
        self.access_key_secret = settings.ALIYUN_ACCESS_KEY_SECRET
        self.oss_endpoint = settings.OSS_ENDPOINT
        self.oss_bucket_name = settings.OSS_BUCKET
        self.oss_prefix = settings.OSS_PREFIX

    async def initialize(self):
        """
        初始化存储服务
        """
        if self.initialized:
            return

        try:
            # 检查必要的配置
            if not self.access_key_id or not self.access_key_secret:
                logger.warning("阿里云访问密钥未配置，存储服务将使用模拟模式")
                self.initialized = True
                return

            # 初始化OSS客户端
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.oss_client = oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)
            self.oss_bucket = self.oss_client

            # 测试连接
            try:
                self.oss_bucket.get_bucket_info()
                logger.info(f"存储服务初始化完成，Bucket: {self.oss_bucket_name}")
            except Exception as e:
                logger.warning(f"OSS Bucket连接测试失败，可能Bucket不存在或无权限: {str(e)}")
                logger.info("存储服务初始化完成（模拟模式）")

            self.initialized = True

        except Exception as e:
            logger.error(f"存储服务初始化失败: {str(e)}")
            # 初始化失败不影响服务启动，但存储功能将使用模拟模式
            self.initialized = True

    def is_real_mode(self) -> bool:
        """是否使用真实的OSS服务"""
        return bool(self.access_key_id and self.access_key_secret and self.oss_bucket)

    async def upload_audio_file(
        self,
        local_file_path: str,
        object_key: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        上传音频文件到OSS

        Args:
            local_file_path: 本地文件路径
            object_key: OSS对象键（可选，自动生成）
            metadata: 元数据（可选）

        Returns:
            (object_key, public_url) 元组，失败返回 (None, None)
        """
        try:
            # 确保服务已初始化
            if not self.initialized:
                await self.initialize()

            # 生成对象键
            if not object_key:
                file_ext = Path(local_file_path).suffix.lower()
                if not file_ext:
                    file_ext = ".mp3"
                timestamp = datetime.now().strftime("%Y%m%d")
                unique_id = str(uuid.uuid4())
                object_key = f"{self.oss_prefix}{timestamp}/{unique_id}{file_ext}"

            if not self.is_real_mode():
                logger.info("存储模拟模式：模拟上传文件")
                # 模拟返回URL
                public_url = f"https://{self.oss_bucket_name}.{self.oss_endpoint}/{object_key}"
                return object_key, public_url

            # 上传文件（简化逻辑，不添加自定义headers以避免签名不匹配）
            logger.info(f"上传文件到OSS: {object_key}")
            with open(local_file_path, 'rb') as f:
                # 注意：不传递headers参数，让OSS库自动处理Content-Type
                # 忽略metadata参数，避免x-oss-meta-* headers导致签名问题
                result = self.oss_bucket.put_object(object_key, f)

                if result.status != 200:
                    logger.error(f"OSS上传失败，状态码: {result.status}")
                    return None, None

            # 生成公网URL
            public_url = f"https://{self.oss_bucket_name}.{self.oss_endpoint}/{object_key}"

            logger.info(f"文件上传成功: {public_url}")
            return object_key, public_url

        except Exception as e:
            logger.error(f"上传音频文件失败: {str(e)}")
            return None, None

    async def upload_audio_data(
        self,
        audio_data: bytes,
        file_extension: str = ".mp3",
        object_key: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        上传音频二进制数据到OSS

        Args:
            audio_data: 音频二进制数据
            file_extension: 文件扩展名
            object_key: OSS对象键（可选）
            metadata: 元数据（可选）

        Returns:
            (object_key, public_url) 元组
        """
        try:
            # 确保服务已初始化
            if not self.initialized:
                await self.initialize()

            # 生成对象键
            if not object_key:
                timestamp = datetime.now().strftime("%Y%m%d")
                unique_id = str(uuid.uuid4())
                object_key = f"{self.oss_prefix}{timestamp}/{unique_id}{file_extension}"

            if not self.is_real_mode():
                logger.info("存储模拟模式：模拟上传数据")
                public_url = f"https://{self.oss_bucket_name}.{self.oss_endpoint}/{object_key}"
                return object_key, public_url

            # 上传数据（简化逻辑，不添加自定义headers以避免签名不匹配）
            logger.info(f"上传音频数据到OSS: {object_key}")
            # 注意：不传递headers参数，让OSS库自动处理Content-Type
            # 忽略metadata参数，避免x-oss-meta-* headers导致签名问题
            result = self.oss_bucket.put_object(object_key, audio_data)

            if result.status != 200:
                logger.error(f"OSS数据上传失败，状态码: {result.status}")
                return None, None

            # 生成公网URL
            public_url = f"https://{self.oss_bucket_name}.{self.oss_endpoint}/{object_key}"

            logger.info(f"音频数据上传成功: {public_url}")
            return object_key, public_url

        except Exception as e:
            logger.error(f"上传音频数据失败: {str(e)}")
            return None, None

    async def delete_file(self, object_key: str) -> bool:
        """
        删除OSS文件

        Args:
            object_key: OSS对象键

        Returns:
            是否删除成功
        """
        try:
            if not self.is_real_mode():
                logger.info(f"存储模拟模式：模拟删除文件 {object_key}")
                return True

            if not self.initialized:
                await self.initialize()

            result = self.oss_bucket.delete_object(object_key)
            if result.status == 204:
                logger.info(f"文件删除成功: {object_key}")
                return True
            else:
                logger.error(f"文件删除失败，状态码: {result.status}")
                return False

        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
            return False

    async def get_file_url(self, object_key: str) -> Optional[str]:
        """
        获取文件公网URL

        Args:
            object_key: OSS对象键

        Returns:
            公网URL，失败返回None
        """
        try:
            if not self.initialized:
                await self.initialize()

            if not self.is_real_mode():
                # 使用自定义域名或标准域名
                if hasattr(settings, 'OSS_PUBLIC_DOMAIN') and settings.OSS_PUBLIC_DOMAIN:
                    return f"{settings.OSS_PUBLIC_DOMAIN}/{object_key}"
                return f"https://{self.oss_bucket_name}.{self.oss_endpoint}/{object_key}"

            # 检查文件是否存在
            try:
                self.oss_bucket.get_object_meta(object_key)
                # 使用自定义域名或标准域名
                if hasattr(settings, 'OSS_PUBLIC_DOMAIN') and settings.OSS_PUBLIC_DOMAIN:
                    public_url = f"{settings.OSS_PUBLIC_DOMAIN}/{object_key}"
                else:
                    public_url = f"https://{self.oss_bucket_name}.{self.oss_endpoint}/{object_key}"
                return public_url
            except oss2.exceptions.NoSuchKey:
                logger.error(f"文件不存在: {object_key}")
                return None

        except Exception as e:
            logger.error(f"获取文件URL失败: {str(e)}")
            return None

    async def generate_presigned_url(
        self,
        object_key: str,
        expiration: int = 3600,
        method: str = "GET",
    ) -> Optional[str]:
        """
        生成预签名URL（用于临时访问）

        Args:
            object_key: OSS对象键
            expiration: 过期时间（秒）
            method: HTTP方法（GET/PUT）

        Returns:
            预签名URL，失败返回None
        """
        try:
            if not self.is_real_mode():
                logger.info("存储模拟模式：无法生成预签名URL")
                return None

            if not self.initialized:
                await self.initialize()

            # 生成预签名URL
            url = self.oss_bucket.sign_url(method, object_key, expiration)
            logger.debug(f"生成预签名URL: {url}")
            return url

        except Exception as e:
            logger.error(f"生成预签名URL失败: {str(e)}")
            return None

    async def get_bucket_info(self) -> Optional[dict]:
        """
        获取Bucket信息

        Returns:
            Bucket信息字典，失败返回None
        """
        try:
            if not self.is_real_mode():
                logger.info("存储模拟模式：无法获取Bucket信息")
                return None

            if not self.initialized:
                await self.initialize()

            info = self.oss_bucket.get_bucket_info()
            return {
                "name": info.name,
                "location": info.location,
                "creation_date": info.creation_date,
                "storage_class": info.storage_class,
                "extranet_endpoint": info.extranet_endpoint,
                "intranet_endpoint": info.intranet_endpoint,
            }

        except Exception as e:
            logger.error(f"获取Bucket信息失败: {str(e)}")
            return None


# 全局存储服务实例
storage_service = StorageService()


async def init_storage_service():
    """
    初始化存储服务（在应用启动时调用）
    """
    await storage_service.initialize()


async def upload_audio_file_to_oss(
    local_file_path: str,
    object_key: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    上传音频文件到OSS（便捷函数）
    """
    return await storage_service.upload_audio_file(local_file_path, object_key, metadata)


async def upload_audio_data_to_oss(
    audio_data: bytes,
    file_extension: str = ".mp3",
    object_key: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    上传音频二进制数据到OSS（便捷函数）
    """
    return await storage_service.upload_audio_data(
        audio_data, file_extension, object_key, metadata
    )


async def delete_oss_file(object_key: str) -> bool:
    """
    删除OSS文件（便捷函数）
    """
    return await storage_service.delete_file(object_key)


async def get_oss_file_url(object_key: str) -> Optional[str]:
    """
    获取OSS文件公网URL（便捷函数）
    """
    return await storage_service.get_file_url(object_key)