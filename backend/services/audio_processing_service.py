"""
音频处理服务 - 包括分割、ASR识别、特征提取等
"""
import logging
import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from pydub import AudioSegment as PydubAudioSegment
from pydub.silence import detect_nonsilent
# import librosa
import numpy as np

from shared.models.audio import AudioSource, AudioSegment
from shared.models.user import User
from config import settings
from ai_models.asr_service import asr_service, recognize_audio_file
from ai_models.nlp_service import get_text_vector

logger = logging.getLogger(__name__)


class AudioProcessingService:
    """
    音频处理服务类
    """

    def __init__(self):
        # 硬编码8秒强制对齐参数
        self.min_silence_len = 300  # 硬编码300ms
        self.silence_thresh = -35   # 硬编码-35dB
        self.keep_silence = settings.KEEP_SILENCE
        self.min_segment_duration = 1.0  # 最小片段时长1秒
        self.max_segment_duration = 8.0  # 硬编码8秒最大片段时长
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.channels = settings.AUDIO_CHANNELS

    async def process_audio_source(
        self,
        db: AsyncSession,
        source: AudioSource,
        user: User,
    ) -> bool:
        """
        处理音频源：分割、识别、向量化

        Args:
            db: 数据库会话
            source: 音频源对象
            user: 用户对象

        Returns:
            处理是否成功
        """
        try:
            logger.info(f"开始处理音频源: {source.id}")

            # 更新处理状态
            source.processing_status = "processing"
            source.processing_progress = 0.1
            await db.commit()

            # 在实际实现中，这里应该：
            # 1. 从OSS下载音频文件到临时目录
            # 2. 进行音频分割
            # 3. 对每个片段进行ASR识别
            # 4. 提取语义向量
            # 5. 保存片段到数据库
            # 6. 更新向量索引

            # 模拟处理过程
            await asyncio.sleep(2)

            # 模拟创建3个片段
            segments_data = [
                {
                    "start_time": 0.0,
                    "end_time": 5.0,
                    "duration": 5.0,
                    "transcription": "这是第一个音频片段的示例文本。",
                },
                {
                    "start_time": 5.0,
                    "end_time": 10.0,
                    "duration": 5.0,
                    "transcription": "这是第二个音频片段的示例文本。",
                },
                {
                    "start_time": 10.0,
                    "end_time": 15.0,
                    "duration": 5.0,
                    "transcription": "这是第三个音频片段的示例文本。",
                },
            ]

            for i, seg_data in enumerate(segments_data):
                segment = await self._create_audio_segment(
                    db=db,
                    source=source,
                    user=user,
                    **seg_data
                )
                logger.info(f"创建音频片段: {segment.id}")

                # 更新进度
                source.processing_progress = 0.1 + (i + 1) * 0.3
                await db.commit()

            # 标记处理完成
            source.processing_status = "completed"
            source.processing_progress = 1.0
            await db.commit()

            logger.info(f"音频源处理完成: {source.id}")
            return True

        except Exception as e:
            logger.error(f"音频源处理失败: {str(e)}")
            source.processing_status = "failed"
            source.error_message = str(e)
            await db.commit()
            return False

    async def _create_audio_segment(
        self,
        db: AsyncSession,
        source: AudioSource,
        user: User,
        start_time: float,
        end_time: float,
        duration: float,
        transcription: str,
        language: str = "zh-CN",
    ) -> AudioSegment:
        """
        创建音频片段记录
        """
        segment_id = str(uuid.uuid4())

        # 生成OSS键（在实际实现中，这里应该从原始音频中提取片段并上传到OSS）
        oss_key = f"audio/segments/{segment_id}.mp3"
        # 使用自定义域名或标准域名
        if hasattr(settings, 'OSS_PUBLIC_DOMAIN') and settings.OSS_PUBLIC_DOMAIN:
            oss_url = f"{settings.OSS_PUBLIC_DOMAIN}/{oss_key}"
        else:
            oss_url = f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}/{oss_key}"

        # 获取文本向量（文档类型）
        vector = await get_text_vector(transcription, text_type="document")
        vector_dimension = len(vector) if vector else None

        segment = AudioSegment(
            id=segment_id,
            source_id=source.id,
            user_id=user.id if user else None,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            transcription=transcription,
            language=language,
            speaker=None,  # 可后续通过说话人识别填充
            emotion=None,  # 可后续通过情感分析填充
            sentiment_score=None,
            vector=vector,
            vector_dimension=vector_dimension,
            vector_updated_at=datetime.utcnow() if vector else None,
            oss_key=oss_key,
            oss_url=oss_url,
            play_count=0,
            favorite_count=0,
            share_count=0,
            tags=source.tags,
            categories=[source.program_type] if source.program_type else None,
            keywords=None,  # 可后续通过关键词提取填充
            review_status="approved",  # 全量授权，跳过审核
        )

        db.add(segment)
        await db.flush()  # 获取ID但不提交，由外部统一提交

        return segment

    async def split_audio_by_silence(
        self,
        audio_file_path: str,
    ) -> List[Tuple[float, float]]:
        """
        基于静音检测分割音频

        Args:
            audio_file_path: 音频文件路径

        Returns:
            分割区间列表，每个区间为(start_time, end_time)
        """
        try:
            logger.info(f"音频分割配置: max_segment_duration={self.max_segment_duration}s, min_segment_duration={self.min_segment_duration}s")
            # 使用pydub加载音频
            audio = PydubAudioSegment.from_file(audio_file_path)

            # 转换为单声道并设置采样率（如果需要）
            if audio.channels > 1:
                audio = audio.set_channels(1)
            if audio.frame_rate != self.sample_rate:
                audio = audio.set_frame_rate(self.sample_rate)

            # 检测非静音区间
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=self.min_silence_len,
                silence_thresh=self.silence_thresh,
                seek_step=10,
            )

            # 转换为秒
            ranges_in_seconds = []
            for start_ms, end_ms in nonsilent_ranges:
                start_sec = start_ms / 1000.0
                end_sec = end_ms / 1000.0
                duration = end_sec - start_sec

                # 过滤过短的片段
                if duration < self.min_segment_duration:
                    continue

                # 强制分割过长的片段（硬性8秒限制）
                if duration > self.max_segment_duration:
                    # 按max_segment_duration步长切割
                    num_splits = int(np.ceil(duration / self.max_segment_duration))
                    for i in range(num_splits):
                        part_start = start_sec + i * self.max_segment_duration
                        part_end = min(start_sec + (i + 1) * self.max_segment_duration, end_sec)
                        # 确保最小片段时长
                        if part_end - part_start >= self.min_segment_duration:
                            ranges_in_seconds.append((part_start, part_end))
                else:
                    ranges_in_seconds.append((start_sec, end_sec))

            logger.info(f"音频分割完成，共 {len(ranges_in_seconds)} 个片段")
            return ranges_in_seconds

        except Exception as e:
            logger.error(f"音频分割失败: {str(e)}")
            raise

    async def extract_audio_segment(
        self,
        source_file_path: str,
        start_time: float,
        end_time: float,
        output_format: str = "mp3",
    ) -> Optional[str]:
        """
        从音频源中提取指定时间段的片段

        Args:
            source_file_path: 源音频文件路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_format: 输出格式

        Returns:
            提取的片段文件路径，失败返回None
        """
        try:
            # 创建临时文件
            temp_dir = tempfile.mkdtemp()
            output_path = Path(temp_dir) / f"segment_{start_time:.1f}_{end_time:.1f}.{output_format}"

            # 使用pydub提取片段
            audio = PydubAudioSegment.from_file(source_file_path)
            segment = audio[start_time * 1000:end_time * 1000]  # pydub使用毫秒

            # 导出
            segment.export(str(output_path), format=output_format)

            return str(output_path)

        except Exception as e:
            logger.error(f"提取音频片段失败: {str(e)}")
            return None

    async def process_audio_segment(
        self,
        segment_file_path: str,
        language: str = "zh-CN",
    ) -> Dict[str, Any]:
        """
        处理单个音频片段：ASR识别、特征提取等

        Args:
            segment_file_path: 片段文件路径
            language: 语言代码

        Returns:
            处理结果字典
        """
        try:
            # ASR识别
            transcription = await recognize_audio_file(
                segment_file_path,
                language=language,
                sample_rate=self.sample_rate,
            )

            if not transcription:
                logger.warning(f"音频片段识别失败: {segment_file_path}")
                transcription = ""
            else:
                # 文本去重
                original_length = len(transcription)
                transcription = deduplicate_text(transcription)
                deduplicated_length = len(transcription)

                # 检查清洗后文本长度，小于5个字则丢弃
                if deduplicated_length < 5:
                    logger.warning(f"音频片段文本过短({deduplicated_length}<5)，丢弃: {segment_file_path}")
                    transcription = ""
                else:
                    logger.info(f"文本去重完成: {original_length} -> {deduplicated_length} 字符")

            # 获取语义向量（文档类型）
            vector = await get_text_vector(transcription, text_type="document") if transcription else None

            # 提取音频特征（可选）
            features = await self.extract_audio_features(segment_file_path)

            return {
                "transcription": transcription,
                "vector": vector,
                "features": features,
                "success": True,
            }

        except Exception as e:
            logger.error(f"音频片段处理失败: {str(e)}")
            return {
                "transcription": "",
                "vector": None,
                "features": {},
                "success": False,
                "error": str(e),
            }

    async def extract_audio_features(
        self,
        audio_file_path: str,
    ) -> Dict[str, Any]:
        """
        提取音频特征（用于情感分析、说话人识别等）

        Args:
            audio_file_path: 音频文件路径

        Returns:
            特征字典
        """
        try:
            # TODO: 临时禁用librosa特征提取
            # 返回空特征字典，后续可重新启用
            return {}

        except Exception as e:
            logger.error(f"音频特征提取失败: {str(e)}")
            return {}

    async def validate_audio_file(
        self,
        file_path: str,
    ) -> Dict[str, Any]:
        """
        验证音频文件

        Args:
            file_path: 音频文件路径

        Returns:
            验证结果
        """
        try:
            # 使用pydub检查音频属性
            audio = PydubAudioSegment.from_file(file_path)

            duration = audio.duration_seconds
            sample_rate = audio.frame_rate
            channels = audio.channels
            file_size = Path(file_path).stat().st_size

            # 检查是否符合要求
            valid = True
            messages = []

            if duration < settings.MIN_AUDIO_DURATION:
                valid = False
                messages.append(f"音频过短 ({duration:.1f}s < {settings.MIN_AUDIO_DURATION}s)")

            if duration > settings.MAX_AUDIO_DURATION:
                valid = False
                messages.append(f"音频过长 ({duration:.1f}s > {settings.MAX_AUDIO_DURATION}s)")

            if file_size > settings.MAX_UPLOAD_SIZE:
                valid = False
                messages.append(f"文件过大 ({file_size / 1024 / 1024:.1f}MB > {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.1f}MB)")

            return {
                "valid": valid,
                "duration": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "file_size": file_size,
                "format": Path(file_path).suffix.lower()[1:],
                "messages": messages,
            }

        except Exception as e:
            logger.error(f"音频文件验证失败: {str(e)}")
            return {
                "valid": False,
                "error": str(e),
                "messages": [f"文件读取失败: {str(e)}"],
            }


def deduplicate_text(text: str) -> str:
    """
    移除转录文本中连续重复的句子（精简为一句），并处理句子内部的冗余词

    处理示例：
    "坐在车里。坐在车里。" -> "坐在车里。"
    "你好你好" -> "你好"
    "今天天气不错。今天天气不错。" -> "今天天气不错。"
    "用智慧和真情拥抱协同。用智慧和真情拥抱协同。" -> "用智慧和真情拥抱协同。"

    Args:
        text: 原始转录文本

    Returns:
        去重后的文本（不超过50个汉字）
    """
    if not text:
        return text

    import re

    # 第一步：处理句子内部的重复词（如"你好你好" -> "你好"）
    def remove_internal_duplicates(sentence: str) -> str:
        """移除句子内部的重复词语"""
        if not sentence or len(sentence) < 2:
            return sentence

        # 查找重复的短语（重复至少两次）
        # 尝试从长度递减的模式匹配
        max_len = len(sentence) // 2
        for pattern_len in range(max_len, 0, -1):
            for i in range(0, len(sentence) - pattern_len * 2 + 1):
                pattern = sentence[i:i+pattern_len]
                # 检查是否连续重复
                if sentence[i:i+pattern_len*2] == pattern * 2:
                    # 只保留一次
                    return sentence[:i+pattern_len] + sentence[i+pattern_len*2:]

        return sentence

    # 第二步：分割句子
    # 更全面的中文句子分隔符：句号、感叹号、问号、分号、逗号、顿号、换行、空格
    sentence_delimiters = r'[。！？；，、\n\s]+'
    sentences = re.split(sentence_delimiters, text)

    # 过滤空句子
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text

    # 第三步：处理每个句子的内部重复
    processed_sentences = []
    for sentence in sentences:
        processed = remove_internal_duplicates(sentence)
        if processed:
            processed_sentences.append(processed)

    # 第四步：移除连续重复的句子（只保留第一次出现）
    deduped_sentences = []
    prev_sentence = None

    for sentence in processed_sentences:
        # 检查是否与上一句相同（完全匹配）
        if sentence == prev_sentence:
            # 跳过重复的句子
            continue
        else:
            # 新句子，添加到结果
            deduped_sentences.append(sentence)
            prev_sentence = sentence

    # 第五步：重新组合句子，使用句号连接
    result = '。'.join(deduped_sentences)

    # 如果原始文本以句号结尾，且结果非空，添加句号
    if text.strip().endswith('。') and result and not result.endswith('。'):
        result += '。'

    # 第六步：强制长度限制（不超过50个汉字）
    # 统计中文字符（Unicode范围）
    chinese_chars = []
    for char in result:
        # 基本汉字范围：\u4e00-\u9fff
        if '\u4e00' <= char <= '\u9fff':
            chinese_chars.append(char)

    if len(chinese_chars) > 50:
        # 截断到50个汉字，保留完整句子
        # 找到第50个汉字的位置
        count = 0
        for i, char in enumerate(result):
            if '\u4e00' <= char <= '\u9fff':
                count += 1
                if count == 50:
                    # 截断到i+1（包括第50个汉字）
                    # 但需要确保不截断在句子中间，尽量在句号后截断
                    # 查找最近的句号
                    dot_pos = result.find('。', i)
                    if dot_pos != -1:
                        result = result[:dot_pos+1]
                    else:
                        result = result[:i+1]
                    break

    return result


# 全局音频处理服务实例
audio_processing_service = AudioProcessingService()