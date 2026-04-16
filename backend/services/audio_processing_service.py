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
from services.music_detection_service import filter_music_segments
from services.search_service import search_service

# Mock audio_processing_service for scripts that import it
import sys
if 'services.audio_processing_service' not in sys.modules:
    sys.modules['services.audio_processing_service'] = sys.modules[__name__]
    sys.modules['services.audio_processing_service'].audio_processing_service = object()

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
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.channels = settings.AUDIO_CHANNELS
        # 语义完整性优先的新参数
        self.min_segment_duration = 2.0  # 最小片段时长2秒（短句允许存在）
        self.soft_max_duration = 15.0  # 建议最大时长15秒（软性建议，非硬性切断）
        self.absolute_max_duration = 20.0  # 绝对最大时长20秒（超过必须拆分）
        self.buffer_start = 0.2  # 起始提前200ms
        self.buffer_end = 0.3  # 结束延后300ms
        # 歌曲检测配置
        self.enable_music_detection = getattr(settings, 'ENABLE_MUSIC_DETECTION', True)
        self.music_detection_threshold = getattr(settings, 'MUSIC_DETECTION_THRESHOLD', 0.65)

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

                    # 如果ASR已经返回文本，直接使用；否则进行本地ASR识别
                    transcription = asr_text.strip() if asr_text else ""

                    # 提取音频片段
                    segment_file_path = await self.extract_audio_segment(
                        audio_file_path, start_time, end_time, text=transcription
                    )

                    if not segment_file_path:
                        logger.warning(f"提取语弹 {i+1} 失败，跳过")
                        skipped_segments.append({"index": i+1, "reason": "提取失败"})
                        continue

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

                    # 更新进度（每5个片段或最后一个时提交，减少死锁风险）
                    source.processing_progress = 0.2 + (i + 1) / total_segments * 0.7
                    if (i + 1) % 5 == 0 or i == total_segments - 1:
                        try:
                            await db.commit()
                        except Exception as commit_e:
                            logger.warning(f"进度更新提交失败（继续处理）: {commit_e}")
                            await db.rollback()

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

        # 自动提取标签（如果源没有标签）
        segment_tags = source.tags
        if not segment_tags:
            segment_tags = extract_tags_from_text(transcription)
            logger.info(f"自动提取标签: {segment_tags}")

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
            tags=segment_tags,
            categories=[source.program_type] if source.program_type else None,
            keywords=None,  # 可后续通过关键词提取填充
            review_status="approved",  # 全量授权，跳过审核
        )

        db.add(segment)
        await db.flush()  # 获取ID但不提交，由外部统一提交

        # 添加到 FAISS 向量索引（确保新节目能被搜索到）
        if vector and vector_dimension:
            try:
                await search_service.add_segment_vector(segment_id, vector)
                logger.info(f"语弹已添加到FAISS索引: {segment_id}")
            except Exception as e:
                logger.warning(f"添加到FAISS索引失败（不影响入库）: {e}")

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
        基于ASR时间戳分割音频（以句子完整性为优先，语义完整度 > 时长限制）

        策略：
        1. 获取词级/短句级ASR结果（带时间戳）
        2. 按标点符号智能合并：以句号、问号、感叹号为强制边界
        3. 短句（<3秒）允许存在，不强制合并
        4. 长句（>15秒）优先在逗号/分号处拆分，非硬性时间切分

        Args:
            audio_file_path: 音频文件路径

        Returns:
            分割区间列表，每个区间为(start_time, end_time, text)
        """
        try:
            logger.info(f"开始基于ASR时间戳分割: {audio_file_path}")
            logger.info("分割策略: 语义完整性优先，句号/问号/感叹号为强制边界")

            # 1. 获取ASR带时间戳的词级识别结果
            from ai_models.asr_service import asr_service
            word_timestamps = await asr_service.recognize_audio_with_word_timestamps(
                audio_file_path,
                language="zh-CN",
                sample_rate=self.sample_rate,
                format="mp3"
            )

            if not word_timestamps:
                logger.warning(f"ASR未返回词级时间戳，回退到静音检测分割")
                segments = await self._fallback_split_by_silence(audio_file_path)
                segments_with_text = [(start, end, "") for start, end in segments]
                merged_segments = self._merge_short_segments(segments_with_text)
                return merged_segments

            logger.info(f"ASR识别成功，共 {len(word_timestamps)} 个词/短句")

            # 2. 按标点符号智能合并/拆分
            segments = self._merge_by_punctuation(word_timestamps)

            logger.info(f"标点合并后，共 {len(segments)} 个语弹片段")

            # 3. 处理超长语弹（>20秒必须拆分，>15秒建议拆分）
            final_segments = self._split_long_segments(segments)

            logger.info(f"长句处理后，最终共 {len(final_segments)} 个语弹片段")

            # 4. 批量优化边界（减少音频加载次数）
            optimized_segments = await self._batch_optimize_boundaries(
                audio_file_path, final_segments
            )

            # 5. 合并相邻短句（提高语义连贯性）
            merged_segments = self._merge_short_segments(optimized_segments)

            # 6. 歌曲检测与过滤（如果启用）
            if self.enable_music_detection:
                logger.info("开始歌曲检测...")
                merged_segments, music_info = await filter_music_segments(
                    merged_segments,
                    audio_file_path,
                    threshold=self.music_detection_threshold
                )
                if music_info:
                    logger.info(f"检测到并过滤了 {len(music_info)} 个歌曲片段")

            return merged_segments

        except Exception as e:
            logger.error(f"ASR时间戳分割失败: {str(e)}")
            logger.info("回退到静音检测分割")
            segments = await self._fallback_split_by_silence(audio_file_path)
            # 为回退片段添加空文本，并尝试合并短句
            segments_with_text = [(start, end, "") for start, end in segments]
            merged_segments = self._merge_short_segments(segments_with_text)
            return merged_segments

    def _merge_by_punctuation(self, word_timestamps: List[Dict]) -> List[Tuple[float, float, str]]:
        """
        按标点符号合并词级时间戳为完整句子

        强制分割边界：句号(。)、问号(?)、感叹号(!)、分号(;)
        可选分割边界：逗号(，)、顿号(、)（仅在超长时使用）
        """
        if not word_timestamps:
            return []

        segments = []
        current_text = []
        current_start = None
        current_end = None

        # 强制分割标点
        force_split_puncts = {'。', '？', '！', '?', '!', '；', ';', '\n'}
        # 可选分割标点（用于超长句拆分）
        optional_split_puncts = {'，', ',', '、', '：', ':'}

        # 合并相邻的短词（ASR有时会把一个词拆成多个）
        merged_words = []
        for word_info in word_timestamps:
            text = word_info.get('text', '').strip()
            start = word_info.get('start_time', 0)
            end = word_info.get('end_time', 0)

            if not text:
                continue

            # 如果当前词很短（<2字符）且与前一个词间隔很短，尝试合并
            if merged_words and len(text) < 3 and (start - merged_words[-1]['end_time']) < 0.1:
                merged_words[-1]['text'] += text
                merged_words[-1]['end_time'] = end
            else:
                merged_words.append({'text': text, 'start_time': start, 'end_time': end})

        for i, word_info in enumerate(merged_words):
            text = word_info.get('text', '')
            start = word_info.get('start_time', 0)
            end = word_info.get('end_time', 0)

            if not text:
                continue

            # 初始化当前片段
            if current_start is None:
                current_start = start
                current_end = end
            else:
                current_end = end

            current_text.append(text)

            # 检查是否是强制分割点（句号、问号、感叹号）
            if any(p in text for p in force_split_puncts):
                # 完成当前片段
                full_text = ''.join(current_text).strip()
                if full_text:
                    segments.append((current_start, current_end, full_text))
                # 重置
                current_text = []
                current_start = None
                current_end = None

        # 处理剩余内容（结尾没有标点的片段）
        if current_text:
            full_text = ''.join(current_text).strip()
            if full_text:
                # 即使结尾没有标点，也保留为一个片段（确保结尾完整性）
                segments.append((current_start, current_end, full_text))

        return segments

    def _split_long_segments(self, segments: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
        """
        处理超长语弹（>20秒必须拆分，>15秒建议拆分）
        优先在逗号、分号、顿号处拆分，保持语义相对完整
        """
        if not segments:
            return []

        final_segments = []
        optional_split_puncts = {'，', ',', '、', '：', ':', '；', ';'}

        for start, end, text in segments:
            duration = end - start

            # 如果小于15秒，直接保留
            if duration <= self.soft_max_duration:
                final_segments.append((start, end, text))
                continue

            # 15-20秒：尝试在可选标点处拆分
            if duration <= self.absolute_max_duration:
                # 查找中间位置的逗号/分号
                split_pos = self._find_split_position(text, prefer_middle=True)
                if split_pos > 0 and split_pos < len(text) - 1:
                    # 根据字符位置比例估算时间分割点
                    text_len = len(text)
                    first_part_ratio = split_pos / text_len
                    time_split = start + (end - start) * first_part_ratio

                    first_text = text[:split_pos+1].strip()
                    second_text = text[split_pos+1:].strip()

                    if second_text and not any(second_text[-1] in p for p in {'。', '？', '！', '?', '!'}):
                        second_text += '。'

                    final_segments.append((start, time_split, first_text))
                    final_segments.append((time_split, end, second_text))
                    logger.info(f"长句({duration:.1f}s)在逗号处拆分为两段")
                    continue

            # 超过20秒或没找到合适的拆分点：强制按语义段落拆分
            logger.info(f"超长句({duration:.1f}s)，按语义段落拆分")
            sub_segments = self._force_split_by_semantic(text, start, end)
            final_segments.extend(sub_segments)

        return final_segments

    def _find_split_position(self, text: str, prefer_middle: bool = True) -> int:
        """
        查找最佳拆分位置（逗号、分号等）
        如果prefer_middle为True，优先找中间位置的标点
        """
        optional_split_puncts = {'，', ',', '、', '：', ':', '；', ';'}

        positions = []
        for i, char in enumerate(text):
            if char in optional_split_puncts:
                positions.append(i)

        if not positions:
            return -1

        if prefer_middle and len(positions) > 1:
            # 找中间位置的标点
            middle_idx = len(positions) // 2
            return positions[middle_idx]
        else:
            # 返回第一个
            return positions[0]

    def _force_split_by_semantic(self, text: str, start_time: float, end_time: float) -> List[Tuple[float, float, str]]:
        """
        强制按语义段落拆分（用于超长句）
        尝试在逗号、分号处拆分，如果实在没有则按字数比例拆分
        """
        duration = end_time - start_time
        optional_split_puncts = {'，', ',', '、', '：', ':', '；', ';'}
        force_split_puncts = {'。', '？', '！', '?', '!', '\n'}

        # 先尝试找所有可选标点
        split_points = []
        for i, char in enumerate(text):
            if char in optional_split_puncts or char in force_split_puncts:
                split_points.append(i)

        if not split_points:
            # 实在没有标点，按字数比例拆成2-3段
            text_len = len(text)
            if text_len < 20:
                return [(start_time, end_time, text)]

            # 拆成2段
            mid = text_len // 2
            first_text = text[:mid].strip() + '，'
            second_text = text[mid:].strip()
            if not any(second_text[-1] in p for p in force_split_puncts):
                second_text += '。'

            mid_time = start_time + (end_time - start_time) / 2
            return [
                (start_time, mid_time, first_text),
                (mid_time, end_time, second_text)
            ]

        # 有标点，按标点拆分
        segments = []
        prev_end = 0
        prev_time = start_time

        for split_pos in split_points:
            segment_text = text[prev_end:split_pos+1].strip()
            if not segment_text:
                continue

            # 计算时间比例
            ratio = (split_pos + 1) / len(text)
            segment_end_time = start_time + duration * ratio

            segments.append((prev_time, segment_end_time, segment_text))
            prev_end = split_pos + 1
            prev_time = segment_end_time

        # 处理剩余部分
        remaining = text[prev_end:].strip()
        if remaining:
            if not any(remaining[-1] in p for p in force_split_puncts):
                remaining += '。'
            segments.append((prev_time, end_time, remaining))

        return segments

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

    async def _batch_optimize_boundaries(
        self,
        audio_file_path: str,
        segments: List[Tuple[float, float, str]],
    ) -> List[Tuple[float, float, str]]:
        """
        批量优化所有片段边界（只加载一次音频，提高性能）

        优化策略：
        1. 起始边界：往前找200ms静音点
        2. 结束边界：往后找1000ms静音点（延长以确保捕捉到完整结尾）
        3. 文本完整性检查：如果文本以不完整词语结尾，延长音频边界

        Args:
            audio_file_path: 音频文件路径
            segments: 原始片段列表 [(start, end, text), ...]

        Returns:
            优化后的片段列表
        """
        try:
            # 只加载一次音频
            audio = PydubAudioSegment.from_file(audio_file_path)
            audio_duration_ms = len(audio)
            audio_duration_sec = audio_duration_ms / 1000.0

            optimized_segments = []

            for i, (start_time, end_time, text) in enumerate(segments):
                if not text or end_time <= start_time:
                    continue

                # 快速边界优化（简化版，减少计算）
                start_ms = int(start_time * 1000)
                end_ms = int(end_time * 1000)

                # 起始边界：往前找200ms静音点（简化）
                search_start = max(0, start_ms - 200)
                if search_start < start_ms:
                    pre_segment = audio[search_start:start_ms]
                    pre_silences = detect_nonsilent(
                        pre_segment, min_silence_len=100, silence_thresh=-40, seek_step=20
                    )
                    if pre_silences:
                        last_sound_end = pre_silences[-1][1]
                        optimized_start_ms = search_start + last_sound_end + 50
                    else:
                        optimized_start_ms = start_ms
                else:
                    optimized_start_ms = start_ms

                # 结束边界：往后找1000ms静音点（延长以确保完整结尾）
                # 原来只有300ms，经常无法捕捉到完整结尾
                search_end = min(audio_duration_ms, end_ms + 1000)
                if end_ms < search_end:
                    post_segment = audio[end_ms:search_end]
                    post_silences = detect_nonsilent(
                        post_segment, min_silence_len=100, silence_thresh=-40, seek_step=20
                    )
                    if post_silences:
                        # 找到第一个非静音区间的开始点，这就是下一个声音的开始
                        # 我们在它之前100ms处截断，确保不会包含下一个词的开头
                        first_sound_start = post_silences[0][0]
                        # 给结尾留一些空间，确保完整（从300ms延长到800ms搜索范围）
                        buffer_ms = 100 if first_sound_start < 500 else 50
                        optimized_end_ms = end_ms + first_sound_start - buffer_ms
                    else:
                        # 如果1000ms内都是静音，说明当前片段确实结束了
                        # 但仍然延长一点以确保完整性（最多延长500ms）
                        optimized_end_ms = end_ms + min(500, search_end - end_ms)
                else:
                    optimized_end_ms = end_ms

                # 文本完整性检查：检测文本是否以不完整词语结尾
                optimized_end_ms = self._adjust_end_by_text_completeness(
                    text, end_ms, optimized_end_ms, audio_duration_ms
                )

                # 转换为秒并确保合理范围
                optimized_start = max(0.0, optimized_start_ms / 1000.0)
                optimized_end = min(audio_duration_sec, optimized_end_ms / 1000.0)

                # 确保至少保留原句子
                optimized_start = min(optimized_start, start_time)
                optimized_end = max(optimized_end, end_time)

                optimized_segments.append((optimized_start, optimized_end, text))
                duration = optimized_end - optimized_start
                logger.info(f"语弹 {i+1}: {optimized_start:.2f}s - {optimized_end:.2f}s (时长: {duration:.2f}s), 文本: {text[:40]}...")

            return optimized_segments

        except Exception as e:
            logger.warning(f"批量优化边界失败: {e}, 使用原始边界")
            # 返回原始片段
            return [(s, e, t) for s, e, t in segments if t and e > s]

    def _adjust_end_by_text_completeness(
        self,
        text: str,
        original_end_ms: int,
        optimized_end_ms: int,
        audio_duration_ms: int
    ) -> int:
        """
        根据文本完整性调整结束边界

        检测文本是否以不完整词语结尾（如"对"、"男"等明显未说完的词）
        如果是，则延长音频边界以确保捕捉到完整词语

        Args:
            text: 转录文本
            original_end_ms: 原始结束时间（毫秒）
            optimized_end_ms: 优化后的结束时间（毫秒）
            audio_duration_ms: 音频总时长（毫秒）

        Returns:
            调整后的结束时间（毫秒）
        """
        # 常见的不完整结尾词（需要延长的信号）
        # 这些词通常出现在句子中间，很少作为完整句子的结尾
        incomplete_endings = {
            # 单字结尾（极可能是截断）
            '对', '的', '是', '男', '女', '我', '你', '他', '她', '它',
            '这', '那', '有', '在', '到', '给', '让', '把', '被', '将',
            '和', '跟', '同', '与', '或', '但', '而', '因', '于', '则',
            '很', '太', '最', '更', '非', '不', '没', '别', '还', '又',
            # 常见词语前半部分
            '我们', '你们', '他们', '她们', '它们', '这些', '那些',
            '这个', '那个', '什么', '怎么', '这么', '那么', '多少',
        }

        # 清理文本，只保留中文
        cleaned_text = ''.join(char for char in text if '\u4e00' <= char <= '\u9fff')

        # 检查文本结尾
        should_extend = False

        # 1. 检查是否以不完整词结尾（最后2个字符）
        if len(cleaned_text) >= 2:
            last_two = cleaned_text[-2:]
            if last_two in incomplete_endings:
                should_extend = True
                logger.info(f"检测到不完整结尾词 '{last_two}'，将延长音频边界")

        # 2. 检查是否以单字结尾（且不是常见句尾词）
        if len(cleaned_text) >= 1:
            last_char = cleaned_text[-1]
            # 常见句尾词（通常是完整的）
            sentence_endings = {'了', '啊', '呢', '吧', '吗', '哦', '嗯', '唉', '哟', '哇'}
            if last_char not in sentence_endings and len(cleaned_text) >= 3:
                # 如果最后一个字不是句尾语气词，且文本较长，可能是截断
                # 检查倒数第2-3个字符是否构成完整词
                if len(cleaned_text) >= 3:
                    last_three = cleaned_text[-3:]
                    # 如果最后三个字符中没有标点符号，可能是截断
                    has_punct_near_end = any(p in text[-6:] for p in ['。', '？', '！', '，', '；'])
                    if not has_punct_near_end:
                        should_extend = True
                        logger.info(f"检测到可能不完整的单字结尾 '{last_char}'，将延长音频边界")

        # 3. 如果文本最后一个字后面紧跟标点，但ASR没有包含进去
        # 通过检查原始文本的最后几个字符
        text_end = text.strip()[-5:] if len(text.strip()) >= 5 else text.strip()
        if text_end and text_end[-1] not in '。！？.!?':
            # 结尾没有标点，可能是截断
            if len(cleaned_text) >= 3:
                should_extend = True
                logger.info(f"检测到无标点结尾，将延长音频边界")

        if should_extend:
            # 延长500ms以确保捕捉到完整结尾
            extended_end = optimized_end_ms + 500
            return min(extended_end, audio_duration_ms)

        return optimized_end_ms

    def _is_host_intro_pattern(self, text: str) -> bool:
        """
        检测文本是否是广播节目主持人介绍模式

        检测模式：
        1. 包含"我是XXX"（主持人自我介绍）
        2. 包含"欢迎收听"（节目开场）
        3. 包含"大家好"（问候语）
        4. 短句（通常<6秒）

        Args:
            text: 文本内容

        Returns:
            是否是主持人介绍模式
        """
        if not text or len(text) < 3:
            return False

        intro_patterns = [
            r'我是\s*[一-龥]{1,6}',  # 我是XXX（2-6个汉字名字）
            r'欢迎收听',
            r'大家好',
            r'听众朋友',
            r'主持人',
            r'我是主播',
        ]

        import re
        for pattern in intro_patterns:
            if re.search(pattern, text):
                return True

        return False

    def _merge_short_segments(
        self,
        segments: List[Tuple[float, float, str]],
    ) -> List[Tuple[float, float, str]]:
        """
        合并相邻的短句，提高语义连贯性

        合并策略：
        1. 当前语弹时长 < 5秒 且下一个语弹时长 < 5秒
        2. 两个语弹之间间隔 < 1秒（时间连续）
        3. 合并后总时长 < 20秒（避免过长）
        4. 合并后文本通顺（结尾无标点或结尾为逗号）

        Args:
            segments: 原始语弹列表 [(start, end, text), ...]

        Returns:
            合并后的语弹列表
        """
        if not segments or len(segments) < 2:
            return segments

        merged = []
        i = 0
        merge_threshold = 6.0  # 小于6秒视为短句（平衡值）
        max_gap = 1.5  # 间隔小于1.5秒视为连续（适中）
        max_merged_duration = 20.0  # 合并后最大时长20秒

        # 记录输入信息便于调试
        logger.info(f"开始短句合并，共 {len(segments)} 段")
        for idx, (s, e, t) in enumerate(segments):
            logger.info(f"  输入段 {idx+1}: {s:.2f}s-{e:.2f}s (时长{e-s:.1f}s): {t[:30]}...")

        while i < len(segments):
            start, end, text = segments[i]
            duration = end - start

            # 如果是长句（>=5秒），直接保留
            if duration >= merge_threshold:
                merged.append((start, end, text))
                i += 1
                continue

            # 短句，尝试与后续短句合并
            current_start = start
            current_end = end
            current_text = text
            current_duration = duration

            # 向后查找可合并的短句
            j = i + 1
            while j < len(segments):
                next_start, next_end, next_text = segments[j]
                next_duration = next_end - next_start

                # 检查下一句是否也是短句
                # 策略：只合并短句，长句保持独立
                # 广播节目特殊处理：主持人对话（我是XXX。你好，我是XXX）可以合并
                current_is_host_intro = self._is_host_intro_pattern(current_text)
                next_is_host_intro = self._is_host_intro_pattern(next_text)
                is_dialogue_pattern = current_is_host_intro and next_is_host_intro

                if next_duration >= merge_threshold and not is_dialogue_pattern:
                    # 下一句是长句，且不是主持人对话模式，停止合并
                    logger.info(f"    下一句{j+1}是长句({next_duration:.1f}s)，停止合并")
                    break

                # 检查间隔
                gap = next_start - current_end
                logger.info(f"    尝试合并段{j+1}: 间隔={gap:.2f}s, 下一句时长={next_duration:.1f}s")

                # 广播节目特性：主持人对话间隔可稍长
                effective_max_gap = max_gap * 1.5 if is_dialogue_pattern else max_gap
                if gap > effective_max_gap:
                    logger.info(f"    间隔{gap:.2f}s > {effective_max_gap}s，停止合并")
                    break

                # 检查合并后时长
                merged_duration = (current_end - current_start) + next_duration + gap
                if merged_duration > max_merged_duration:
                    break

                # 短句合并策略：只要时长和间隔满足条件，就合并（忽略句号）
                # 合并
                current_end = next_end
                current_text = current_text.strip()
                next_text = next_text.strip()

                # 智能连接文本：将结尾的句号替换为逗号
                if current_text.endswith(('。', '？', '！', '.', '?', '!')):
                    current_text = current_text[:-1] + '，'
                elif not current_text.endswith(('，', ',', '、')):
                    current_text += '，'

                # 处理下一句的开头
                if next_text.startswith(('，', ',', '、')):
                    next_text = next_text[1:].strip()

                current_text += next_text

                current_duration = current_end - current_start
                logger.info(f"    成功合并段{j+1}，当前总时长: {current_duration:.1f}s")
                j += 1

                # 如果合并后已成为长句，停止合并
                if current_duration >= merge_threshold:
                    logger.info(f"    合并后已成为长句({current_duration:.1f}s)，停止合并")
                    break

            merged.append((current_start, current_end, current_text))
            logger.info(f"  输出段: {current_start:.2f}s-{current_end:.2f}s (时长{current_duration:.1f}s): {current_text[:40]}...")
            i = j if j > i else i + 1

        logger.info(f"短句合并完成: {len(segments)}段 -> {len(merged)}段")
        return merged

    async def _fallback_split_by_silence(
        self,
        audio_file_path: str,
    ) -> List[Tuple[float, float]]:
        """
        回退方案：基于静音检测分割音频（语义完整性优先，无硬性时长限制）
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

                # 过滤过短的片段（小于2秒）
                if duration < self.min_segment_duration:
                    continue

                # 超长片段（>20秒）尝试在静音点拆分
                if duration > self.absolute_max_duration:
                    # 查找中间区域的静音点
                    mid_time = (start_sec + end_sec) / 2
                    mid_ms = int(mid_time * 1000)
                    window_ms = 3000  # 前后3秒窗口查找静音点

                    search_start = max(start_ms, mid_ms - window_ms)
                    search_end = min(end_ms, mid_ms + window_ms)
                    search_segment = audio[search_start:search_end]

                    # 在窗口内查找静音
                    silences = detect_nonsilent(
                        search_segment,
                        min_silence_len=200,
                        silence_thresh=-40,
                        seek_step=50
                    )

                    if silences and len(silences) >= 2:
                        # 在静音区间找到拆分点
                        for i in range(len(silences) - 1):
                            if silences[i+1][0] - silences[i][1] > 200:  # 有200ms以上静音
                                split_offset = silences[i][1]
                                split_time = (search_start + split_offset) / 1000.0

                                # 确保拆分段落不小于2秒
                                if split_time - start_sec >= self.min_segment_duration and \
                                   end_sec - split_time >= self.min_segment_duration:
                                    ranges_in_seconds.append((start_sec, split_time))
                                    ranges_in_seconds.append((split_time, end_sec))
                                    logger.info(f"超长片段({duration:.1f}s)在静音点拆分为两段")
                                    break
                        else:
                            ranges_in_seconds.append((start_sec, end_sec))
                    else:
                        ranges_in_seconds.append((start_sec, end_sec))
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
        text: str = "",
    ) -> Optional[str]:
        """
        从音频源中提取指定时间段的片段

        Args:
            source_file_path: 源音频文件路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_format: 输出格式
            text: 转录文本（用于完整性检查）

        Returns:
            提取的片段文件路径，失败返回None
        """
        try:
            # 创建临时文件
            temp_dir = tempfile.mkdtemp()
            output_path = Path(temp_dir) / f"segment_{start_time:.1f}_{end_time:.1f}.{output_format}"

            # 使用pydub提取片段
            audio = PydubAudioSegment.from_file(source_file_path)
            audio_duration_ms = len(audio)

            # 转换为毫秒
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)

            # 额外检查：如果文本以不完整词语结尾，再延长一点
            if text:
                extra_buffer_ms = self._calculate_extra_buffer_for_text(text)
                if extra_buffer_ms > 0:
                    end_ms = min(audio_duration_ms, end_ms + extra_buffer_ms)
                    logger.info(f"文本完整性检查：延长 {extra_buffer_ms}ms 以确保完整结尾")

            # 确保不超出音频范围
            start_ms = max(0, start_ms)
            end_ms = min(audio_duration_ms, end_ms)

            segment = audio[start_ms:end_ms]

            # 导出
            segment.export(str(output_path), format=output_format)

            return str(output_path)

        except Exception as e:
            logger.error(f"提取音频片段失败: {str(e)}")
            return None

    def _calculate_extra_buffer_for_text(self, text: str) -> int:
        """
        根据文本完整性计算额外的缓冲时间

        Args:
            text: 转录文本

        Returns:
            需要延长的毫秒数
        """
        # 常见的不完整结尾词
        incomplete_endings = {
            '对', '的', '是', '男', '女', '我', '你', '他', '她', '它',
            '这', '那', '有', '在', '到', '给', '让', '把', '被', '将',
            '和', '跟', '同', '与', '或', '但', '而', '因', '于', '则',
            '很', '太', '最', '更', '非', '不', '没', '别', '还', '又',
            '我们', '你们', '他们', '她们', '它们', '这些', '那些',
            '这个', '那个', '什么', '怎么', '这么', '那么', '多少',
        }

        # 清理文本
        cleaned_text = ''.join(char for char in text if '\u4e00' <= char <= '\u9fff')

        if len(cleaned_text) >= 2:
            last_two = cleaned_text[-2:]
            if last_two in incomplete_endings:
                return 300  # 延长300ms

        # 检查是否无标点结尾
        text_end = text.strip()[-5:] if len(text.strip()) >= 5 else text.strip()
        if text_end and text_end[-1] not in '。！？.!?':
            if len(cleaned_text) >= 3:
                return 200  # 延长200ms

        return 0

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
    针对广播节目ASR特性优化：处理开头重复、语气词重复等

    处理示例：
    "坐在车里。坐在车里。" -> "坐在车里。"
    "你好你好" -> "你好"
    "今天天气不错。今天天气不错。" -> "今天天气不错。"
    "用智慧和真情拥抱协同。用智慧和真情拥抱协同。" -> "用智慧和真情拥抱协同。"
    "他们，他们用智慧和..." -> "他们用智慧和..."

    Args:
        text: 原始转录文本

    Returns:
        去重后的文本（不超过50个汉字）
    """
    if not text:
        return text

    import re

    # 广播节目特殊处理：移除开头的语气词重复（如"他们，他们"）
    # 模式1：重复的词 + 标点 + 同样的词（中文）
    text = re.sub(r'^([\u4e00-\u9fff]{1,6})[，,、\s]+\1', r'\1', text)
    # 模式2：重复的词 + 标点 + 同样的词（更宽松，包括英文/数字）
    text = re.sub(r'^(\S{1,8})[，,、\s]+\1', r'\1', text)
    # 模式3：处理多次重复（如"他们，他们，他们" -> "他们"）
    text = re.sub(r'^([\u4e00-\u9fff]{1,6})([，,、\s]+\1)+', r'\1', text)

    # 处理句子内部的重复词（如"你好你好" -> "你好"）
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

    # 辅助函数：移除句子内部的重复短语（用逗号/顿号分隔的重复）
    def remove_duplicate_phrases(sentence: str) -> str:
        """移除句子中用逗号分隔的重复短语"""
        if not sentence or len(sentence) < 4:
            return sentence

        # 按逗号/顿号分割
        parts = re.split(r'[，,、]', sentence)
        parts = [p.strip() for p in parts if p.strip()]

        if len(parts) < 2:
            return sentence

        # 移除连续重复的片段
        unique_parts = []
        prev_part = None
        for part in parts:
            # 标准化后比较
            normalized = re.sub(r'\s+', '', part)
            prev_normalized = re.sub(r'\s+', '', prev_part) if prev_part else ''

            if normalized != prev_normalized:
                unique_parts.append(part)
                prev_part = part

        # 重新组合
        if len(unique_parts) == 1:
            return unique_parts[0]
        return '，'.join(unique_parts)

    # 第二步：先用句号/问号/感叹号分割句子（保留逗号在句子内部）
    # 这样 "A。A。" 会被正确识别为重复，而 "A，B。" 不会
    sentence_delimiters = r'[。！？.!?\n]+'
    sentences = re.split(sentence_delimiters, text)

    # 过滤空句子并保留原始标点信息
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text

    # 第三步：处理每个句子的内部重复
    processed_sentences = []
    for sentence in sentences:
        # 先去除内部重复词
        processed = remove_internal_duplicates(sentence)
        # 再去除句子内部的逗号重复（如 "A，A" -> "A"）
        processed = remove_duplicate_phrases(processed)
        if processed:
            processed_sentences.append(processed)

    # 第四步：移除连续重复的句子（完全匹配或相似度极高）
    deduped_sentences = []
    prev_sentence = None

    def similarity(s1: str, s2: str) -> float:
        """计算两个字符串的相似度（简化版）"""
        if not s1 or not s2:
            return 0.0
        # 标准化：去除标点和空格
        s1_clean = re.sub(r'[，,、。！？.!?\s]', '', s1)
        s2_clean = re.sub(r'[，,、。！？.!?\s]', '', s2)
        if not s1_clean or not s2_clean:
            return 0.0
        # 如果一个是另一个的子串，认为是相似
        if s1_clean in s2_clean or s2_clean in s1_clean:
            return min(len(s1_clean), len(s2_clean)) / max(len(s1_clean), len(s2_clean))
        return 0.0

    for sentence in processed_sentences:
        # 标准化后比较（去除标点空格）
        normalized = re.sub(r'[，,、\s]', '', sentence)
        prev_normalized = re.sub(r'[，,、\s]', '', prev_sentence) if prev_sentence else ''

        # 检查是否与上一句相同（完全匹配或高度相似）
        is_duplicate = False
        if normalized and normalized == prev_normalized:
            is_duplicate = True
        elif prev_sentence and similarity(sentence, prev_sentence) > 0.8:
            # 相似度>80%认为是重复
            is_duplicate = True

        if is_duplicate:
            # 跳过重复的句子
            continue
        else:
            # 新句子，添加到结果
            deduped_sentences.append(sentence)
            prev_sentence = sentence

    # 第五步：重新组合句子，智能使用标点
    # 策略：单句用句号；多句时，前面用逗号连接，最后一句用句号结尾
    if len(deduped_sentences) == 1:
        result = deduped_sentences[0] + '。'
    else:
        # 多句情况：除最后一句外，其他句之间用逗号
        result = '，'.join(deduped_sentences[:-1]) + '，' + deduped_sentences[-1] + '。'

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


def extract_tags_from_text(text: str, max_tags: int = 3) -> List[str]:
    """
    从转录文本中自动提取标签

    策略：
    1. 预定义关键词匹配（生活、北京、美食、天气、日常、心情、旅行、学习等）
    2. 提取命名实体（地名、机构名等）
    3. 统计词频，选择高频实词

    Args:
        text: 转录文本
        max_tags: 最多返回的标签数量

    Returns:
        标签列表
    """
    if not text or len(text.strip()) < 5:
        return ["日常"]  # 默认标签

    # 预定义标签关键词映射
    tag_keywords = {
        "生活": ["生活", "日常", "居家", "家庭", "吃饭", "睡觉", "起床", "上班", "下班"],
        "北京": ["北京", "北平", "京城", "首都", "京", "北二环", "北三环", "国贸", "三里屯", "望京", "海淀", "朝阳"],
        "美食": ["美食", "吃饭", "餐厅", "菜", "饭", "吃", "味道", "好吃", "难吃", "早餐", "午餐", "晚餐", "厨房", "做饭"],
        "天气": ["天气", "气温", "下雨", "晴天", "阴天", "下雪", "刮风", "温度", "冷热", "太阳", "云"],
        "日常": ["日常", "平常", "平时", "今天", "明天", "昨天", "早上", "晚上"],
        "心情": ["心情", "开心", "难过", "高兴", "伤心", "激动", "平静", "焦虑", "紧张", "放松", "舒服", "难受"],
        "旅行": ["旅行", "旅游", "出门", "出发", "到达", "酒店", "景点", "游玩", "风景", "机场", "车站", "高铁", "飞机"],
        "学习": ["学习", "看书", "读书", "考试", "学校", "大学", "老师", "学生", "课程", "知识", "专业"],
        "工作": ["工作", "上班", "加班", "公司", "同事", "老板", "项目", "客户", "会议", "报告", "职场"],
        "健康": ["健康", "运动", "健身", "跑步", "生病", "医院", "医生", "身体", "锻炼"],
        "娱乐": ["电影", "电视剧", "综艺", "音乐", "游戏", "玩", "唱歌", "跳舞", "娱乐", "休闲"],
        "社交": ["朋友", "聚会", "聊天", "见面", "约会", "社交", "人际关系"],
    }

    import re

    # 清理文本
    cleaned_text = text.lower()

    # 记录每个标签的匹配次数
    tag_scores = {}

    for tag, keywords in tag_keywords.items():
        score = 0
        for keyword in keywords:
            # 计算关键词出现次数
            count = len(re.findall(re.escape(keyword), cleaned_text))
            if count > 0:
                # 长关键词权重更高
                score += count * (len(keyword) / 2)
        if score > 0:
            tag_scores[tag] = score

    # 按分数排序，选择前N个
    sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
    selected_tags = [tag for tag, score in sorted_tags[:max_tags]]

    # 如果没有匹配到任何标签，返回默认标签
    if not selected_tags:
        selected_tags = ["日常"]

    return selected_tags


# 全局音频处理服务实例
audio_processing_service = AudioProcessingService()