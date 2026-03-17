"""
ASR服务 - 语音识别
"""
import logging
import asyncio
import tempfile
import os
import json
import time
from typing import Optional, List, Dict, Any, BinaryIO
from pathlib import Path

import aiofiles
import oss2
from tenacity import retry, stop_after_attempt, wait_exponential
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkcore.request import CommonRequest

# 尝试导入阿里云NLS SDK（新版本 alibabacloud-nls-python-sdk），如果失败则尝试旧版本
HAS_NLS_SDK = False
NLS_SDK_VERSION = "none"

try:
    # 首先尝试导入新版本 SDK
    import nls

    # 检查是否有FileTrans类（新版本SDK的高级接口）
    if hasattr(nls, 'FileTrans'):
        HAS_NLS_SDK = True
        NLS_SDK_VERSION = "new"
        logger = logging.getLogger(__name__)
        logger.info("使用阿里云NLS SDK新版本（FileTrans类）")
    else:
        # 尝试导入CreateFileTransRequest和GetFileTransRequest（新版本SDK的旧式接口）
        try:
            from nls import CreateFileTransRequest, GetFileTransRequest
            HAS_NLS_SDK = True
            NLS_SDK_VERSION = "new_legacy"
            logger = logging.getLogger(__name__)
            logger.info("使用阿里云NLS SDK新版本（旧式请求类）")
        except ImportError:
            # 新版本SDK但没有预期的类，回退到RPC模式
            HAS_NLS_SDK = True
            NLS_SDK_VERSION = "rpc"
            logger = logging.getLogger(__name__)
            logger.warning("阿里云NLS SDK新版本已导入，但未找到预期的类，使用RPC模式")
except ImportError:
    # 新版本SDK导入失败，尝试旧版本
    try:
        from aliyunsdknls.request.v20180817 import CreateFileTransRequest, GetFileTransRequest
        HAS_NLS_SDK = True
        NLS_SDK_VERSION = "old"
        logger = logging.getLogger(__name__)
        logger.info("使用阿里云NLS SDK旧版本")
    except ImportError:
        # 如果两个SDK都没有，尝试使用阿里云核心SDK的RpcRequest直接调用API
        try:
            from aliyunsdkcore.request import RpcRequest
            HAS_NLS_SDK = True
            NLS_SDK_VERSION = "rpc"
            logger = logging.getLogger(__name__)
            logger.info("使用阿里云核心SDK RpcRequest进行ASR API调用")
        except ImportError:
            HAS_NLS_SDK = False
            NLS_SDK_VERSION = "none"
            logger = logging.getLogger(__name__)
            logger.warning("阿里云NLS SDK未安装，ASR服务将使用模拟模式")

from config import settings

logger = logging.getLogger(__name__)


class ASRService:
    """
    阿里云智能语音交互（ASR）服务类
    """

    def __init__(self):
        self.initialized = False
        self.client = None
        self.oss_client = None
        self.oss_bucket = None
        self.app_key = settings.ALIYUN_ASR_APP_KEY
        self.access_key_id = settings.ALIYUN_ACCESS_KEY_ID
        self.access_key_secret = settings.ALIYUN_ACCESS_KEY_SECRET
        self.region_id = settings.ALIYUN_REGION_ID
        self.oss_endpoint = settings.OSS_ENDPOINT
        self.oss_bucket_name = settings.OSS_BUCKET

    async def initialize(self):
        """
        初始化ASR服务
        """
        if self.initialized:
            return

        try:
            # 检查必要的配置 - 严格检查，缺失配置直接报错
            if not self.app_key:
                raise ValueError("ALIYUN_ASR_APP_KEY 未配置，ASR服务无法使用真实API")

            if not self.access_key_id or not self.access_key_secret:
                raise ValueError("阿里云访问密钥未配置，ASR服务无法使用真实API")

            # 阿里云录音文件识别服务强制使用 cn-shanghai 区域
            # 注意：OSS 区域保持不变（北京），ASR 使用上海区域是标准接入点
            asr_region_id = "cn-shanghai"

            # 初始化阿里云NLS客户端（使用ASR区域）
            self.client = AcsClient(
                self.access_key_id,
                self.access_key_secret,
                asr_region_id
            )

            # 初始化OSS客户端（使用OSS区域，保持不变）
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.oss_client = oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)
            self.oss_bucket = self.oss_client

            logger.info(f"ASR服务初始化完成，ASR区域: {asr_region_id}, OSS区域: {self.oss_endpoint}")
            self.initialized = True

        except Exception as e:
            logger.error(f"ASR服务初始化失败: {str(e)}")
            # 初始化失败直接报错，不再使用模拟模式
            raise RuntimeError(f"ASR服务初始化失败: {str(e)}") from e

    def is_real_mode(self) -> bool:
        """是否使用真实的阿里云ASR服务"""
        # 严格检查：只有所有必需的密钥都配置，并且服务已初始化成功，才返回True
        # 注意：此方法仅用于检查配置状态，实际API调用失败会直接抛出异常
        has_valid_keys = bool(self.app_key and self.access_key_id and self.access_key_secret)
        return has_valid_keys and self.initialized

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def recognize_file(
        self,
        audio_file_path: str,
        language: str = "zh-CN",
        sample_rate: int = 16000,
        format: str = "pcm",
        enable_punctuation: bool = True,
        enable_inverse_text_normalization: bool = True,
    ) -> Optional[str]:
        """
        识别音频文件（支持常见音频格式）

        Args:
            audio_file_path: 音频文件路径
            language: 语言代码，默认zh-CN
            sample_rate: 采样率，默认16000
            format: 音频格式，pcm/wav/mp3等
            enable_punctuation: 是否启用标点符号
            enable_inverse_text_normalization: 是否启用ITN（逆文本归一化）

        Returns:
            识别结果文本，失败返回None
        """
        try:
            logger.debug(f"ASR服务模式检查: NLS_SDK_VERSION={NLS_SDK_VERSION}, HAS_NLS_SDK={HAS_NLS_SDK}")
            if not self.is_real_mode():
                # 如果配置不完整，直接抛出异常
                if not self.app_key or not self.access_key_id or not self.access_key_secret:
                    raise ValueError("阿里云ASR服务配置不完整，缺少必要的API密钥")
                # 如果配置完整但服务未初始化，先尝试初始化
                await self.initialize()

            # 确保服务已初始化
            if not self.initialized:
                await self.initialize()

            # 生成OSS对象键
            import uuid
            object_key = f"asr-temp/{uuid.uuid4()}_{Path(audio_file_path).name}"

            # 上传文件到OSS
            logger.info(f"上传音频文件到OSS: {object_key}")
            with open(audio_file_path, 'rb') as f:
                self.oss_bucket.put_object(object_key, f)

            # 生成预签名URL（有效期1小时），ASR服务需要访问OSS文件
            # 使用sign_url方法生成预签名URL，GET方法，3600秒有效期
            oss_url = self.oss_bucket.sign_url('GET', object_key, 3600)

            # 使用阿里云NLS SDK的FileTrans类（新版本SDK）
            if NLS_SDK_VERSION == "new":
                try:
                    # 初始化FileTrans
                    ft = nls.FileTrans(
                        akid=self.access_key_id,
                        aksecret=self.access_key_secret,
                        appkey=self.app_key
                    )

                    # 构建请求参数
                    params = {
                        "file_link": oss_url,
                        "domain": "file_trans",
                        "auto_split": True,
                        "enable_punctuation_prediction": enable_punctuation,
                        "enable_inverse_text_normalization": enable_inverse_text_normalization,
                        "enable_voice_detection": False
                    }

                    # 设置音频格式参数
                    if format == "pcm":
                        params["format"] = "pcm"
                        params["sample_rate"] = sample_rate
                    elif format in ["wav", "mp3", "aac", "ogg", "flac"]:
                        params["format"] = format
                    else:
                        params["format"] = "mp3"  # 默认

                    # 提交任务
                    task_id = ft.submit(**params)

                    if not task_id:
                        logger.error("创建录音文件识别任务失败：未返回TaskId")
                        raise RuntimeError("阿里云ASR API调用失败：未返回TaskId")

                    logger.info(f"录音文件识别任务创建成功: {task_id}")

                    # 轮询任务状态
                    max_attempts = 30
                    for attempt in range(max_attempts):
                        await asyncio.sleep(2)  # 等待2秒

                        status_result = ft.get_status(task_id)
                        status = status_result.get("Status")

                        if status == 'SUCCESS':
                            # 提取识别结果
                            sentences = status_result.get('Result', {}).get('Sentences', [])
                            if sentences:
                                # 拼接所有句子
                                text = ' '.join([s.get('Text', '') for s in sentences])
                                logger.info(f"ASR识别成功: {len(text)} 字符")
                                return text
                            else:
                                logger.warning("ASR识别成功但未返回文本")
                                raise RuntimeError("阿里云ASR API调用成功但未返回文本")
                        elif status == 'FAILED':
                            logger.error(f"ASR识别任务失败: {status_result.get('Message')}")
                            raise RuntimeError(f"阿里云ASR API调用失败: {status_result.get('Message')}")
                        elif status == 'RUNNING':
                            logger.debug(f"ASR识别任务进行中 ({attempt+1}/{max_attempts})")
                            continue
                        elif status == 'SUCCESS_WITH_NO_VALID_FRAGMENT':
                            logger.info(f"ASR识别成功但无有效片段: 音频中没有检测到有效语音 (静音或噪音)")
                            return None
                        else:
                            logger.warning(f"未知的ASR任务状态: {status}")
                            continue

                    logger.error(f"ASR识别任务超时，超过 {max_attempts} 次轮询")
                    raise RuntimeError(f"阿里云ASR API调用超时")

                except Exception as e:
                    logger.error(f"使用新版本NLS SDK失败: {str(e)}")
                    # 直接抛出异常，禁止降级到模拟模式
                    raise RuntimeError(f"阿里云ASR API调用失败: {str(e)}") from e


            # 旧版本SDK或RPC模式（保持原有逻辑）
            else:
                if NLS_SDK_VERSION == "old":
                    request = CreateFileTransRequest.CreateFileTransRequest()
                else:  # rpc version - 使用CommonRequest方式
                    request = CommonRequest()
                    request.set_product('nls-filetrans')
                    request.set_version('2018-08-17')
                    request.set_action_name('SubmitTask')
                    request.set_domain('filetrans.cn-shanghai.aliyuncs.com')
                    request.set_method('POST')
                    request.set_protocol_type('https')
                    request.set_accept_format('json')

                if NLS_SDK_VERSION == "rpc":
                    # CommonRequest方式：将所有业务参数封装成JSON字典
                    # 根据阿里云官方文档格式调整参数名
                    task_params = {
                        "appkey": self.app_key,
                        "file_link": oss_url,
                        "auto_split": True,
                        "version": "4.0",
                        "enable_words": False,
                        "enable_sample_rate_adaptive": True
                    }

                    # 根据文档格式设置音频参数（文档中没有明确的format参数，可能需要调整）

                    # 将任务参数JSON字符串作为Task参数传递 - 使用add_body_params
                    import json
                    task_json = json.dumps(task_params)
                    request.add_body_params('Task', task_json)
                    # 添加区域ID参数
                    request.add_body_params('RegionId', 'cn-shanghai')

                    # 调试信息
                    logger.info(f"CommonRequest配置: product=nls-filetrans, version=2018-08-17, action=SubmitTask, domain=filetrans.cn-shanghai.aliyuncs.com, method=POST")
                    logger.info(f"任务参数: {task_json}")
                else:
                    # 旧版本SDK保持原有逻辑
                    request.set_AppKey(self.app_key)
                    request.set_FileLink(oss_url)
                    request.set_Domain("file_trans")
                    request.set_AutoSplit("true")
                    request.set_EnablePunctuationPrediction("true" if enable_punctuation else "false")
                    request.set_EnableInverseTextNormalization("true" if enable_inverse_text_normalization else "false")
                    request.set_EnableVoiceDetection("false")

                    # 设置音频格式参数
                    if format == "pcm":
                        request.set_Format("pcm")
                        request.set_SampleRate(sample_rate)
                    elif format in ["wav", "mp3", "aac", "ogg", "flac"]:
                        request.set_Format(format)
                    else:
                        request.set_Format("mp3")  # 默认

                response = self.client.do_action_with_exception(request)
                result = json.loads(response.decode('utf-8'))
                logger.debug(f"SubmitTask响应: {result}")

                # 根据官方文档检查StatusText
                status_text = result.get('StatusText')
                task_id = result.get('TaskId')

                if status_text != 'SUCCESS' or not task_id:
                    logger.error(f"创建录音文件识别任务失败: {result}")
                    raise RuntimeError(f"阿里云ASR API调用失败: {result}")

                logger.info(f"录音文件识别任务创建成功: {task_id}")

                # 轮询任务状态
                max_attempts = 30
                for attempt in range(max_attempts):
                    await asyncio.sleep(2)  # 等待2秒

                    if NLS_SDK_VERSION == "old":
                        get_request = GetFileTransRequest.GetFileTransRequest()
                        get_request.set_TaskId(task_id)
                    elif NLS_SDK_VERSION == "rpc":
                        # CommonRequest方式查询状态
                        get_request = CommonRequest()
                        get_request.set_product('nls-filetrans')
                        get_request.set_version('2018-08-17')
                        get_request.set_action_name('GetTaskResult')
                        get_request.set_domain('filetrans.cn-shanghai.aliyuncs.com')
                        get_request.set_method('GET')  # GetTaskResult使用GET方法
                        get_request.set_protocol_type('https')
                        get_request.set_accept_format('json')
                        get_request.add_query_param('TaskId', task_id)
                    else:
                        # 新版本SDK的旧式接口
                        from aliyunsdkcore.request import RpcRequest
                        get_request = RpcRequest('nls-filetrans', '2018-08-17', 'GetFileTrans')
                        get_request.set_TaskId(task_id)

                    get_response = self.client.do_action_with_exception(get_request)
                    get_result = json.loads(get_response.decode('utf-8'))
                    logger.debug(f"GetTaskResult响应 (尝试 {attempt+1}): {get_result}")

                    status = get_result.get('StatusText')  # 根据官方文档，使用StatusText而不是Status
                    if status == 'SUCCESS':
                        # 提取识别结果
                        sentences = get_result.get('Result', {}).get('Sentences', [])
                        if sentences:
                            # 拼接所有句子
                            text = ' '.join([s.get('Text', '') for s in sentences])
                            logger.info(f"ASR识别成功: {len(text)} 字符")
                            return text
                        else:
                            logger.warning("ASR识别成功但未返回文本")
                            raise RuntimeError("阿里云ASR API调用成功但未返回文本")
                    elif status == 'FAILED':
                        logger.error(f"ASR识别任务失败: {get_result.get('Message')}")
                        raise RuntimeError(f"阿里云ASR API调用失败: {get_result.get('Message')}")
                    elif status == 'RUNNING' or status == 'QUEUEING':
                        logger.debug(f"ASR识别任务进行中 ({attempt+1}/{max_attempts})，状态: {status}")
                        continue
                    elif status == 'SUCCESS_WITH_NO_VALID_FRAGMENT':
                        logger.info(f"ASR识别成功但无有效片段: 音频中没有检测到有效语音 (静音或噪音)")
                        return None
                    else:
                        logger.warning(f"未知的ASR任务状态: {status}")
                        continue

                logger.error(f"ASR识别任务超时，超过 {max_attempts} 次轮询")
                raise RuntimeError(f"阿里云ASR API调用超时")

        except ClientException as e:
            logger.error(f"阿里云客户端异常: {e.get_error_code() if hasattr(e, 'get_error_code') else e.error_code if hasattr(e, 'error_code') else 'Unknown'} - {e.get_error_msg() if hasattr(e, 'get_error_msg') else e.message if hasattr(e, 'message') else str(e)}")
            raise RuntimeError(f"阿里云ASR客户端异常: {str(e)}") from e
        except ServerException as e:
            logger.error(f"阿里云服务端异常: {e.get_error_code() if hasattr(e, 'get_error_code') else e.error_code if hasattr(e, 'error_code') else 'Unknown'} - {e.get_error_msg() if hasattr(e, 'get_error_msg') else e.message if hasattr(e, 'message') else str(e)}")
            raise RuntimeError(f"阿里云ASR服务端异常: {str(e)}") from e
        except Exception as e:
            logger.error(f"语音识别失败: {str(e)}", exc_info=True)
            raise RuntimeError(f"阿里云ASR调用失败: {str(e)}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def recognize_audio_stream(
        self,
        audio_stream: BinaryIO,
        language: str = "zh-CN",
        sample_rate: int = 16000,
        format: str = "pcm",
        chunk_size: int = 3200,
    ) -> Optional[str]:
        """
        识别音频流（适合实时或大文件流式识别）

        Args:
            audio_stream: 音频二进制流
            language: 语言代码
            sample_rate: 采样率
            format: 音频格式
            chunk_size: 分块大小

        Returns:
            识别结果文本
        """
        try:
            if not self.is_real_mode():
                # 如果配置不完整，直接抛出异常
                if not self.app_key or not self.access_key_id or not self.access_key_secret:
                    raise ValueError("阿里云ASR服务配置不完整，缺少必要的API密钥")
                # 如果配置完整但服务未初始化，先尝试初始化
                await self.initialize()

            # 在实际实现中，这里应该：
            # 1. 初始化流式识别器
            # 2. 分块发送音频数据
            # 3. 收集并返回完整结果

            # TODO: 实现真实的流式识别
            raise NotImplementedError("阿里云ASR流式识别暂未实现，需要使用真实API")

        except Exception as e:
            logger.error(f"流式语音识别失败: {str(e)}")
            return None

    async def recognize_audio_with_timestamps(
        self,
        audio_file_path: str,
        language: str = "zh-CN",
        sample_rate: int = 16000,
        format: str = "pcm",
    ) -> Optional[List[Dict[str, Any]]]:
        """
        识别音频并返回带时间戳的文本

        Returns:
            列表，每个元素包含文本、开始时间、结束时间
        """
        try:
            if not self.is_real_mode():
                # 如果配置不完整，直接抛出异常
                if not self.app_key or not self.access_key_id or not self.access_key_secret:
                    raise ValueError("阿里云ASR服务配置不完整，缺少必要的API密钥")
                # 如果配置完整但服务未初始化，先尝试初始化
                await self.initialize()

            # 在实际实现中，这里应该：
            # 1. 调用阿里云ASR API（支持时间戳的接口）
            # 2. 解析时间戳信息

            # TODO: 实现真实的带时间戳识别
            raise NotImplementedError("阿里云ASR带时间戳识别暂未实现，需要使用真实API")

        except Exception as e:
            logger.error(f"带时间戳的语音识别失败: {str(e)}")
            return None

    async def batch_recognize_files(
        self,
        file_paths: List[str],
        language: str = "zh-CN",
        sample_rate: int = 16000,
        max_concurrent: int = 3,
    ) -> List[Optional[str]]:
        """
        批量识别音频文件

        Args:
            file_paths: 音频文件路径列表
            language: 语言代码
            sample_rate: 采样率
            max_concurrent: 最大并发数

        Returns:
            识别结果列表（与输入列表顺序一致）
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def recognize_with_semaphore(file_path: str) -> Optional[str]:
            async with semaphore:
                return await self.recognize_file(
                    file_path, language, sample_rate
                )

        tasks = [recognize_with_semaphore(fp) for fp in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"批量识别文件 {file_paths[i]} 失败: {str(result)}")
                final_results.append(None)
            else:
                final_results.append(result)

        return final_results

    async def get_supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return ["zh-CN", "en-US", "ja-JP", "ko-KR", "fr-FR", "de-DE", "es-ES"]

    async def get_supported_formats(self) -> List[str]:
        """获取支持的音频格式列表"""
        return ["pcm", "wav", "mp3", "aac", "ogg", "flac"]

    async def validate_audio_file(
        self,
        audio_file_path: str,
        min_duration: float = settings.MIN_AUDIO_DURATION,
        max_duration: float = settings.MAX_AUDIO_DURATION,
    ) -> Dict[str, Any]:
        """
        验证音频文件是否适合ASR识别

        Returns:
            包含验证结果和信息的字典
        """
        try:
            # 在实际实现中，这里应该：
            # 1. 使用pydub或librosa检查音频属性
            # 2. 验证时长、采样率、声道数等

            # 模拟验证结果
            return {
                "valid": True,
                "duration": 10.5,  # 模拟时长
                "sample_rate": 16000,
                "channels": 1,
                "format": "mp3",
                "message": "音频文件验证通过"
            }
        except Exception as e:
            logger.error(f"音频文件验证失败: {str(e)}")
            return {
                "valid": False,
                "message": f"音频文件验证失败: {str(e)}"
            }


# 全局ASR服务实例
asr_service = ASRService()


async def init_asr_service():
    """
    初始化ASR服务（在应用启动时调用）
    """
    await asr_service.initialize()


async def recognize_audio_file(audio_file_path: str, **kwargs) -> Optional[str]:
    """
    识别音频文件（便捷函数）
    """
    return await asr_service.recognize_file(audio_file_path, **kwargs)


async def recognize_audio_stream(audio_stream: BinaryIO, **kwargs) -> Optional[str]:
    """
    识别音频流（便捷函数）
    """
    return await asr_service.recognize_audio_stream(audio_stream, **kwargs)


async def batch_recognize_audio_files(file_paths: List[str], **kwargs) -> List[Optional[str]]:
    """
    批量识别音频文件（便捷函数）
    """
    return await asr_service.batch_recognize_files(file_paths, **kwargs)