"""
音频处理服务 - 包括分割、ASR识别、特征提取等
"""
import logging
import asyncio
import tempfile
import shutil
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
from services.quality_check import check_segment_quality
from services.emotion_service import analyze_emotion

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

            # 获取音频文件路径
            audio_file_path = source.oss_url
            if not Path(audio_file_path).exists():
                logger.error(f"音频文件不存在: {audio_file_path}")
                source.processing_status = "failed"
                source.error_message = "音频文件不存在"
                await db.commit()
                return False

            # 验证音频文件
            validation = await self.validate_audio_file(audio_file_path)
            if not validation["valid"]:
                logger.error(f"音频文件验证失败: {validation['messages']}")
                source.processing_status = "failed"
                source.error_message = f"音频文件验证失败: {'; '.join(validation['messages'])}"
                await db.commit()
                return False

            # 更新音频源信息
            source.duration = validation["duration"]
            source.sample_rate = validation["sample_rate"]
            source.channels = validation["channels"]
            source.file_size = validation["file_size"]
            source.processing_progress = 0.2
            await db.commit()

            # 进行音频分割
            logger.info(f"开始分割音频: {audio_file_path}")
            segments_ranges = await self.split_audio_by_silence(audio_file_path)

            if not segments_ranges:
                logger.warning("音频分割未返回任何片段")
                source.processing_status = "failed"
                source.error_message = "音频分割失败，未识别到有效片段"
                await db.commit()
                return False

            logger.info(f"音频分割完成，共 {len(segments_ranges)} 个片段")

            # 处理每个片段
            total_segments = len(segments_ranges)
            created_segments = []
            skipped_segments = []

            for i, segment_data in enumerate(segments_ranges):
                try:
                    # 新的返回格式: (start_time, end_time, text)
                    if len(segment_data) == 3:
                        start_time, end_time, asr_text = segment_data
                    else:
                        # 兼容旧格式 (start_time, end_time)
                        start_time, end_time = segment_data[:2]
                        asr_text = ""

                    duration = end_time - start_time
                    logger.info(f"处理语弹 {i+1}/{total_segments}: {start_time:.2f}s - {end_time:.2f}s")

                    # 提取音频片段
                    segment_file_path = await self.extract_audio_segment(
                        audio_file_path, start_time, end_time
                    )

                    if not segment_file_path:
                        logger.warning(f"提取语弹 {i+1} 失败，跳过")
                        skipped_segments.append({"index": i+1, "reason": "提取失败"})
                        continue

                    # 如果ASR已经返回文本，直接使用；否则进行本地ASR识别
                    transcription = asr_text.strip() if asr_text else ""

                    if not transcription:
                        # 回退到本地ASR识别
                        result = await self.process_audio_segment(segment_file_path)
                        if result["success"] and result["transcription"]:
                            transcription = result["transcription"]

                    if not transcription:
                        logger.warning(f"语弹 {i+1} 无文本内容，跳过")
                        skipped_segments.append({"index": i+1, "reason": "无文本"})
                        # 清理临时文件
                        self._cleanup_temp_file(segment_file_path)
                        continue

                    # 质量检查
                    is_quality_ok, quality_result = await check_segment_quality(transcription, duration)

                    if not is_quality_ok:
                        logger.warning(f"语弹 {i+1} 质量检查不通过: {quality_result.get('reasons', [])}")
                        skipped_segments.append({
                            "index": i+1,
                            "reason": f"质量不合格: {quality_result.get('reasons', [])}"
                        })
                        # 清理临时文件，不入库
                        self._cleanup_temp_file(segment_file_path)
                        continue

                    logger.info(f"语弹 {i+1} 质量评分: {quality_result.get('score', 0):.1f} ({quality_result.get('quality_level', '未知')})")

                    # 情感分析
                    emotion_result = await analyze_emotion(transcription)
                    emotion = emotion_result.get("emotion", "neutral")
                    sentiment_score = emotion_result.get("score", 0.0)

                    logger.info(f"语弹 {i+1} 情感分析: {emotion} (得分: {sentiment_score:.2f})")

                    # 创建音频片段记录
                    segment = await self._create_audio_segment(
                        db=db,
                        source=source,
                        user=user,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        transcription=transcription,
                        segment_file_path=segment_file_path,
                        emotion=emotion,
                        sentiment_score=sentiment_score,
                    )
                    created_segments.append(segment)
                    logger.info(f"创建精品语弹: {segment.id}")

                    # 更新进度
                    source.processing_progress = 0.2 + (i + 1) / total_segments * 0.7
                    await db.commit()

                except Exception as seg_e:
                    logger.error(f"处理语弹 {i+1} 时出错: {seg_e}")
                    skipped_segments.append({"index": i+1, "reason": f"异常: {str(seg_e)}"})
                    continue

            # 记录处理结果
            logger.info(f"裁切完成: 成功 {len(created_segments)} 个, 跳过 {len(skipped_segments)} 个")
            if skipped_segments:
                logger.info(f"跳过的语弹: {skipped_segments}")

            # 标记处理完成
            if created_segments:
                source.processing_status = "completed"
                source.processing_progress = 1.0
                logger.info(f"音频源处理完成: {source.id}, 共创建 {len(created_segments)} 个精品语弹")
            else:
                source.processing_status = "failed"
                source.error_message = "未成功创建任何音频片段（可能都被质量检查过滤）"
                logger.warning(f"音频源处理未创建任何片段: {source.id}")

            await db.commit()
            return created_segments

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
        segment_file_path: str,
        language: str = "zh-CN",
        emotion: str = None,
        sentiment_score: float = None,
    ) -> AudioSegment:
        """
        创建音频片段记录
        """
        segment_id = str(uuid.uuid4())

        # 上传音频片段到OSS
        oss_key = f"audio/segments/{segment_id}.mp3"
        oss_url = None

        try:
            from services.storage_service import upload_audio_file_to_oss
            uploaded_key, uploaded_url = await upload_audio_file_to_oss(
                local_file_path=segment_file_path,
                object_key=oss_key,
            )
            if uploaded_url:
                oss_url = uploaded_url
                oss_key = uploaded_key or oss_key
                logger.info(f"音频片段上传成功: {oss_url}")
            else:
                logger.warning(f"音频片段上传失败，使用构造URL: {oss_key}")
        except Exception as e:
            logger.error(f"上传音频片段到OSS失败: {e}")

        # 如果上传失败，使用构造的URL
        if not oss_url:
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
            emotion=emotion,
            sentiment_score=sentiment_score,
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

        # 清理临时文件
        try:
            if segment_file_path and Path(segment_file_path).exists():
                temp_dir = Path(segment_file_path).parent
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug(f"清理临时文件: {temp_dir}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

        return segment

    async def split_audio_by_silence(
        self,
        audio_file_path: str,
    ) -> List[Tuple[float, float, str]]:
        """
        基于ASR时间戳分割音频（以句子完整性为优先，去掉时长约束）

        Args:
            audio_file_path: 音频文件路径

        Returns:
            分割区间列表，每个区间为(start_time, end_time, text)
        """
        try:
            logger.info(f"开始基于ASR时间戳分割: {audio_file_path}")
            logger.info("分割策略: 以句子完整性为优先，每个语弹一个完整句子")

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
                segments = await self._fallback_split_by_silence(audio_file_path)
                # 为回退方案添加空文本
                return [(start, end, "") for start, end in segments]

            logger.info(f"ASR识别成功，共 {len(sentences)} 个句子")

            # 2. 加载音频用于静音检测（找句子边界）
            audio = PydubAudioSegment.from_file(audio_file_path)
            audio_duration = len(audio) / 1000.0  # 毫秒转秒

            # 3. 为每个句子优化边界（基于静音检测找呼吸感）
            optimized_segments = []
            for i, sent in enumerate(sentences):
                text = sent.get('text', '').strip()
                start_time = sent.get('start_time', 0)
                end_time = sent.get('end_time', 0)

                if not text or end_time <= start_time:
                    continue

                # 优化边界：在句子前后找静音点
                optimized_start, optimized_end = await self._optimize_segment_boundaries(
                    audio, start_time, end_time, i, len(sentences)
                )

                optimized_segments.append((optimized_start, optimized_end, text))
                logger.debug(f"句子 {i+1}: {optimized_start:.2f}s - {optimized_end:.2f}s, 文本: {text[:30]}...")

            logger.info(f"分割完成，共 {len(optimized_segments)} 个语弹片段")

            # 4. 验证结果
            for i, (start, end, text) in enumerate(optimized_segments):
                duration = end - start
                logger.info(f"语弹 {i+1}: {start:.2f}s - {end:.2f}s (时长: {duration:.2f}s)")

            return optimized_segments

        except Exception as e:
            logger.error(f"ASR时间戳分割失败: {str(e)}")
            logger.info("回退到静音检测分割")
            segments = await self._fallback_split_by_silence(audio_file_path)
            return [(start, end, "") for start, end in segments]

    async def _optimize_segment_boundaries(
        self,
        audio: PydubAudioSegment,
        start_time: float,
        end_time: float,
        index: int,
        total: int,
    ) -> Tuple[float, float]:
        """
        优化片段边界：基于静音检测找最佳截取点，确保呼吸感

        策略：
        1. 在句子开始前找最近的静音点（提前最多300ms）
        2. 在句子结束后找最近的静音点（延后最多500ms）
        3. 确保不会跨句

        Args:
            audio: pydub AudioSegment 对象
            start_time: 句子开始时间（秒）
            end_time: 句子结束时间（秒）
            index: 句子索引
            total: 总句子数

        Returns:
            (optimized_start, optimized_end)
        """
        try:
            # 转换为毫秒
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)

            # 在句子开始前查找静音点（往前最多300ms）
            search_start = max(0, start_ms - 300)
            pre_segment = audio[search_start:start_ms]

            # 检测静音区间
            pre_silences = detect_nonsilent(
                pre_segment,
                min_silence_len=50,  # 50ms的静音即可
                silence_thresh=-40,
                seek_step=10
            )

            if pre_silences:
                # 找到最后一个非静音区间的结束点
                last_sound_end = pre_silences[-1][1]
                # 从search_start开始算，加上偏移量
                optimized_start_ms = search_start + last_sound_end
                # 再加一点缓冲
                optimized_start_ms = min(start_ms, optimized_start_ms + 50)
            else:
                # 没找到静音点，使用原开始时间
                optimized_start_ms = start_ms

            # 在句子结束后查找静音点（往后最多500ms）
            audio_duration_ms = len(audio)
            search_end = min(audio_duration_ms, end_ms + 500)
            post_segment = audio[end_ms:search_end]

            post_silences = detect_nonsilent(
                post_segment,
                min_silence_len=50,
                silence_thresh=-40,
                seek_step=10
            )

            if post_silences:
                # 找到第一个非静音区间的开始点
                first_sound_start = post_silences[0][0]
                # 从end_ms开始算
                optimized_end_ms = end_ms + first_sound_start
                # 减一点缓冲，确保不会截到下一句
                optimized_end_ms = max(end_ms, optimized_end_ms - 100)
            else:
                # 没找到静音点，使用原结束时间
                optimized_end_ms = end_ms

            # 确保合理的时长
            optimized_start = max(0.0, optimized_start_ms / 1000.0)
            optimized_end = min(audio_duration_ms / 1000.0, optimized_end_ms / 1000.0)

            # 确保至少保留原句子的主要部分
            optimized_start = min(optimized_start, start_time)
            optimized_end = max(optimized_end, end_time)

            return (optimized_start, optimized_end)


        except Exception as e:
            logger.warning(f"优化边界失败: {e}, 使用原始边界")
            return (start_time, end_time)
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
        emotion: str = None,
        sentiment_score: float = None,
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



    def _cleanup_temp_file(self, file_path: str):
        """清理临时文件"""
        try:
            if file_path and Path(file_path).exists():
                temp_dir = Path(file_path).parent
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug(f"清理临时文件: {temp_dir}")
        except Exception as e:
            logger.warning(f"清理临时文件失败: {e}")

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