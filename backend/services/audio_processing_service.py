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
        # 硬编码8秒强制对齐参数（用于回退方案）
        self.min_silence_len = 300  # 硬编码300ms
        self.silence_thresh = -35   # 硬编码-35dB
        self.keep_silence = settings.KEEP_SILENCE
        self.min_segment_duration = 5.0  # 最小片段时长5秒（新目标）
        self.max_segment_duration = 10.0  # 目标最大片段时长10秒
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.channels = settings.AUDIO_CHANNELS
        # 语义聚拢参数
        self.target_min_duration = 5.0  # 目标最小时长
        self.target_max_duration = 10.0  # 目标最大时长
        self.absolute_max_duration = 12.0  # 绝对最大时长
        self.buffer_start = 0.2  # 起始提前200ms
        self.buffer_end = 0.3  # 结束延后300ms

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
        基于ASR时间戳进行语义聚拢分割音频

        Args:
            audio_file_path: 音频文件路径

        Returns:
            分割区间列表，每个区间为(start_time, end_time)
        """
        try:
            logger.info(f"开始基于ASR时间戳进行语义聚拢分割: {audio_file_path}")
            logger.info(f"目标片段时长: {self.target_min_duration}-{self.target_max_duration}秒，合并规则: 短句合并直到目标时长，最大不超过{self.absolute_max_duration}秒")

            # 1. 获取ASR带时间戳的识别结果
            from ai_models.asr_service import asr_service
            sentences = await asr_service.recognize_audio_with_timestamps(
                audio_file_path,
                language="zh-CN",
                sample_rate=self.sample_rate,
                format="mp3"
            )

            if not sentences:
                logger.warning(f"ASR未返回有效句子，回退到静音检测分割")
                return await self._fallback_split_by_silence(audio_file_path)

            logger.info(f"ASR识别成功，共 {len(sentences)} 个句子")

            # 2. 语义聚拢：合并短句为目标时长片段
            merged_segments = self._merge_sentences_by_duration(sentences)

            # 3. 优化听感：起始提前buffer_start，结束延后buffer_end
            optimized_segments = []
            for start_time, end_time in merged_segments:
                # 确保起始时间不小于0
                new_start = max(0.0, start_time - self.buffer_start)  # 提前
                new_end = end_time + self.buffer_end  # 延后
                optimized_segments.append((new_start, new_end))

            logger.info(f"语义聚拢分割完成，共 {len(optimized_segments)} 个片段")

            # 4. 验证片段时长
            for i, (start, end) in enumerate(optimized_segments):
                duration = end - start
                logger.info(f"片段 {i+1}: {start:.2f}s - {end:.2f}s (时长: {duration:.2f}s)")
                if duration < self.target_min_duration * 0.8:  # 允许80%的误差
                    logger.warning(f"片段 {i+1} 时长过短: {duration:.2f}s < {self.target_min_duration*0.8:.1f}s")
                elif duration > self.absolute_max_duration:
                    logger.warning(f"片段 {i+1} 时长过长: {duration:.2f}s > {self.absolute_max_duration:.1f}s")

            return optimized_segments

        except Exception as e:
            logger.error(f"ASR时间戳分割失败: {str(e)}")
            logger.info("回退到静音检测分割")
            return await self._fallback_split_by_silence(audio_file_path)

    def _merge_sentences_by_duration(self, sentences: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
        """
        根据句子时间戳合并短句为目标时长片段

        合并规则:
        1. 目标时长: 5-10秒
        2. 如果当前句子时长 < 5秒，继续合并下一句
        3. 合并后的总时长不超过12秒
        4. 确保每个片段至少包含一个完整句子

        Args:
            sentences: 句子列表，每个元素包含 text, start_time, end_time

        Returns:
            合并后的片段区间列表 [(start_time, end_time), ...]
        """
        if not sentences:
            return []

        segments = []
        current_start = sentences[0]["start_time"]
        current_end = sentences[0]["end_time"]
        current_texts = [sentences[0]["text"]]

        for i in range(1, len(sentences)):
            sentence = sentences[i]
            sentence_duration = sentence["end_time"] - sentence["start_time"]
            current_duration = current_end - current_start
            potential_duration = sentence["end_time"] - current_start

            # 如果当前片段时长已经达到目标最小时长，且加入下一句会超过绝对最大时长，则结束当前片段
            if current_duration >= self.target_min_duration and potential_duration > self.absolute_max_duration:
                # 保存当前片段
                segments.append((current_start, current_end))
                logger.debug(f"创建片段: {current_start:.2f}s - {current_end:.2f}s (时长: {current_duration:.2f}s), 文本: {'|'.join(current_texts)}")

                # 开始新片段
                current_start = sentence["start_time"]
                current_end = sentence["end_time"]
                current_texts = [sentence["text"]]
                continue

            # 如果当前片段时长小于目标最小时长，继续合并
            if current_duration < self.target_min_duration:
                current_end = sentence["end_time"]
                current_texts.append(sentence["text"])
                continue

            # 当前片段时长在目标范围内，检查是否应该结束
            # 如果下一句很短（小于3秒）且合并后不超过绝对最大时长，可以考虑合并
            if sentence_duration < 3.0 and potential_duration <= self.absolute_max_duration:
                current_end = sentence["end_time"]
                current_texts.append(sentence["text"])
                continue

            # 否则结束当前片段，开始新片段
            segments.append((current_start, current_end))
            logger.debug(f"创建片段: {current_start:.2f}s - {current_end:.2f}s (时长: {current_duration:.2f}s), 文本: {'|'.join(current_texts)}")

            current_start = sentence["start_time"]
            current_end = sentence["end_time"]
            current_texts = [sentence["text"]]

        # 添加最后一个片段
        final_duration = current_end - current_start
        segments.append((current_start, current_end))
        logger.debug(f"创建最后片段: {current_start:.2f}s - {current_end:.2f}s (时长: {final_duration:.2f}s), 文本: {'|'.join(current_texts)}")

        # 过滤过短的片段（小于2秒）
        filtered_segments = []
        for start, end in segments:
            duration = end - start
            if duration >= 2.0:
                filtered_segments.append((start, end))
            else:
                logger.warning(f"过滤过短片段: {start:.2f}s - {end:.2f}s (时长: {duration:.2f}s)")

        logger.info(f"语义聚拢完成: {len(sentences)} 个句子 -> {len(filtered_segments)} 个片段")
        return filtered_segments

    async def _fallback_split_by_silence(
        self,
        audio_file_path: str,
    ) -> List[Tuple[float, float]]:
        """
        回退方案：基于静音检测分割音频
        """
        try:
            logger.info(f"使用静音检测回退分割: {audio_file_path}")
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

            logger.info(f"静音检测分割完成，共 {len(ranges_in_seconds)} 个片段")
            return ranges_in_seconds

        except Exception as e:
            logger.error(f"静音检测分割失败: {str(e)}")
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