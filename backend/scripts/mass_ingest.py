#!/usr/bin/env python3
"""
全格式批量音频入库脚本

功能：
1. 扫描指定目录下所有的 .mp3、.m4a、.wav 文件
2. 格式转换：使用 pydub 读取文件，切片后统一导出为 .mp3 格式存入 OSS
3. 防重复：检查数据库，已处理过的文件名直接跳过
4. 优化 ASR 适配：音频强制转换为 16000Hz, 单声道
5. 生产统计：处理完成后输出统计信息

使用方法：
python mass_ingest.py [扫描目录] [--max-concurrent N] [--dry-run]

默认扫描目录：storage/raw_media/
"""

import asyncio
import sys
import os
import logging
import argparse
from pathlib import Path
from datetime import datetime
import uuid
import hashlib
from typing import List, Dict, Any, Optional, Tuple
import json

# 强制设置音频分割配置，覆盖环境变量
os.environ['MAX_SEGMENT_DURATION'] = '8.0'
os.environ['MIN_SEGMENT_DURATION'] = '1.5'

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 使用MySQL连接，根据运行环境自动选择
import os
if os.environ.get("DATABASE_URL") is None:
    # 检查是否在Docker容器内（通过环境变量或文件系统）
    if os.path.exists("/.dockerenv"):
        # 在容器内，使用服务名mysql
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"
    else:
        # 在主机上，使用localhost
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from shared.database.session import init_db, Base
import shared.database.session as db_session
from shared.models.chat import ChatMessage  # 确保 ChatMessage 模型已注册
from shared.models.audio import AudioSource, AudioSegment
from shared.models.user import User
from services.audio_processing_service import audio_processing_service, deduplicate_text
from services.storage_service import upload_audio_file_to_oss, init_storage_service
from ai_models.asr_service import recognize_audio_file, init_asr_service
from ai_models.nlp_service import get_text_vector, init_nlp_service
from services.search_service import add_audio_segment_to_index, init_vector_index
from config import settings

# 临时调整音频最大时长限制，以通过验证（处理长音频）
settings.MAX_AUDIO_DURATION = 36000.0  # 10小时

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 支持的音频文件扩展名
SUPPORTED_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac'}


def calculate_file_hash(file_path: Path) -> str:
    """计算文件的MD5哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def scan_audio_files(directory: Path) -> List[Path]:
    """扫描目录下的音频文件"""
    audio_files = []

    if not directory.exists():
        logger.error(f"目录不存在: {directory}")
        return audio_files

    for ext in SUPPORTED_EXTENSIONS:
        audio_files.extend(directory.glob(f"*{ext}"))
        audio_files.extend(directory.glob(f"*{ext.upper()}"))

    # 递归扫描子目录
    for subdir in directory.iterdir():
        if subdir.is_dir():
            for ext in SUPPORTED_EXTENSIONS:
                audio_files.extend(subdir.glob(f"*{ext}"))
                audio_files.extend(subdir.glob(f"*{ext.upper()}"))

    # 去重和排序
    audio_files = list(set(audio_files))
    audio_files.sort()

    logger.info(f"在目录 {directory} 中找到 {len(audio_files)} 个音频文件")
    return audio_files


async def check_existing_source(db: AsyncSession, original_filename: str, file_hash: str) -> Optional[AudioSource]:
    """
    检查是否已存在相同的音频源

    检查条件：
    1. 相同的原始文件名
    2. 相同的文件哈希（可选，更严格）
    """
    try:
        # 首先按原始文件名查找
        stmt = select(AudioSource).where(AudioSource.original_filename == original_filename)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"文件 {original_filename} 已存在于数据库，跳过处理")
            # 可以进一步检查文件哈希是否匹配（如果保存了哈希值）
            return existing

        return None
    except Exception as e:
        logger.error(f"检查已存在音频源时出错: {str(e)}")
        return None


async def convert_audio_for_asr(
    input_file_path: Path,
    output_file_path: Path,
    sample_rate: int = 16000,
    channels: int = 1,
    format: str = "mp3"
) -> bool:
    """
    转换音频文件为ASR优化的格式（16000Hz, 单声道）

    返回: 是否转换成功
    """
    try:
        from pydub import AudioSegment as PydubAudioSegment

        logger.info(f"转换音频文件: {input_file_path} -> {output_file_path}")

        # 加载音频文件
        audio = PydubAudioSegment.from_file(str(input_file_path))

        # 转换为单声道
        if audio.channels > 1:
            audio = audio.set_channels(channels)
            logger.debug(f"转换为单声道: {audio.channels} 声道")

        # 设置采样率
        if audio.frame_rate != sample_rate:
            audio = audio.set_frame_rate(sample_rate)
            logger.debug(f"设置采样率: {audio.frame_rate}Hz")

        # 导出为MP3格式
        audio.export(str(output_file_path), format=format, bitrate="64k")

        logger.info(f"音频转换完成: {output_file_path}")
        return True

    except Exception as e:
        logger.error(f"音频转换失败: {str(e)}")
        return False


async def create_audio_source(
    db: AsyncSession,
    audio_file_path: Path,
    file_hash: str
) -> Optional[AudioSource]:
    """创建音频源记录"""
    try:
        # 验证音频文件
        validation = await audio_processing_service.validate_audio_file(str(audio_file_path))

        if not validation.get("valid"):
            logger.error(f"音频文件验证失败: {validation.get('messages', ['未知错误'])}")
            return None

        # 从文件名提取信息
        filename = audio_file_path.name
        title = audio_file_path.stem

        # 尝试从文件名解析节目信息
        program_type = "unknown"
        episode_number = None

        # 简单启发式：根据文件名关键词判断节目类型
        if any(keyword in title for keyword in ["新闻", "广播", "报道"]):
            program_type = "news"
        elif any(keyword in title for keyword in ["娱乐", "音乐", "综艺"]):
            program_type = "entertainment"
        elif any(keyword in title for keyword in ["教育", "学习", "讲座"]):
            program_type = "education"
        elif any(keyword in title for keyword in ["体育", "比赛", "运动"]):
            program_type = "sports"

        # 生成唯一ID
        source_id = str(uuid.uuid4())

        # 生成OSS键
        timestamp = datetime.now().strftime("%Y%m%d")
        oss_key = f"audio/sources/{timestamp}/{source_id}{audio_file_path.suffix}"

        # 使用自定义域名或标准域名
        if hasattr(settings, 'OSS_PUBLIC_DOMAIN') and settings.OSS_PUBLIC_DOMAIN:
            oss_url = f"{settings.OSS_PUBLIC_DOMAIN}/{oss_key}"
        else:
            oss_url = f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}/{oss_key}"

        # 创建音频源对象
        source = AudioSource(
            id=source_id,
            title=title[:200],  # 确保不超过字段长度限制
            description=f"自动导入的音频文件: {filename}",
            program_type=program_type,
            episode_number=episode_number,
            broadcast_date=datetime.utcnow(),
            original_filename=filename,
            file_size=validation["file_size"],
            duration=validation["duration"],
            format=validation["format"],
            sample_rate=validation["sample_rate"],
            channels=validation["channels"],
            oss_key=oss_key,
            oss_url=oss_url,
            processing_status="pending",
            processing_progress=0.0,
            copyright_holder="自动导入",
            license_type="auto_import",
            is_public=True,
            tags=["auto_import", program_type],
            extra_metadata={
                "file_hash": file_hash,
                "import_date": datetime.utcnow().isoformat(),
                "original_path": str(audio_file_path)
            }
        )

        db.add(source)
        await db.flush()
        logger.info(f"创建音频源记录: {source.id} - {title}")

        return source

    except Exception as e:
        logger.error(f"创建音频源记录失败: {str(e)}")
        return None


async def upload_source_to_oss(
    db: AsyncSession,
    source: AudioSource,
    audio_file_path: Path
) -> bool:
    """上传音频源文件到OSS"""
    try:
        logger.info(f"上传音频源文件到OSS: {audio_file_path}")

        # 上传文件
        object_key, public_url = await upload_audio_file_to_oss(
            local_file_path=str(audio_file_path),
            object_key=source.oss_key,
            metadata={
                "source_id": source.id,
                "original_filename": source.original_filename,
                "title": source.title,
                "program_type": source.program_type,
                "import_date": datetime.utcnow().isoformat()
            }
        )

        if not object_key or not public_url:
            logger.error("音频源文件上传失败")
            return False

        # 更新音频源记录
        source.oss_key = object_key
        source.oss_url = public_url
        source.processing_status = "uploaded"
        source.processing_progress = 0.2

        await db.commit()
        logger.info(f"音频源文件上传成功: {public_url}")
        return True

    except Exception as e:
        logger.error(f"音频源文件上传失败: {str(e)}")
        source.processing_status = "failed"
        source.error_message = str(e)
        await db.commit()
        return False


async def process_audio_segments(
    db: AsyncSession,
    source: AudioSource,
    audio_file_path: Path,
    converted_audio_path: Optional[Path] = None
) -> Tuple[int, int]:
    """
    处理音频源，分割为片段并处理

    返回: (成功片段数, 总片段数)
    """
    try:
        logger.info(f"开始处理音频源片段: {source.id}")

        # 更新处理状态
        source.processing_status = "processing"
        source.processing_progress = 0.3
        await db.commit()

        # 使用转换后的音频文件进行分割（如果提供了）
        processing_file_path = converted_audio_path if converted_audio_path else audio_file_path

        # 1. 静音分割
        logger.info("开始静音分割...")
        segments_ranges = await audio_processing_service.split_audio_by_silence(str(processing_file_path))

        if not segments_ranges:
            logger.warning(f"未检测到任何非静音频段: {audio_file_path}")
            source.processing_status = "failed"
            source.error_message = "未检测到任何非静音频段"
            await db.commit()
            return 0, 0

        logger.info(f"静音分割完成，得到 {len(segments_ranges)} 个片段区间")

        # 2. 创建临时存储目录
        segments_dir = backend_dir / "storage" / "segments" / source.id
        segments_dir.mkdir(parents=True, exist_ok=True)

        total_segments = len(segments_ranges)

        # 片段级并发配置：使用信号量限制并发数，避免压垮API
        SEGMENT_CONCURRENCY_LIMIT = 5  # 限制并发数为5，可根据需要调整到10
        semaphore = asyncio.Semaphore(SEGMENT_CONCURRENCY_LIMIT)

        # 共享进度变量（asyncio单线程，安全）
        processed_segments = 0

        async def process_single_segment(segment_index: int, start_time: float, end_time: float) -> bool:
            """处理单个音频片段，返回是否成功"""
            nonlocal processed_segments
            async with semaphore:
                try:
                    logger.info(f"处理片段 {segment_index+1}/{total_segments}: {start_time:.2f}s - {end_time:.2f}s")

                    # 1. 检查是否已存在相同片段（断点续传）
                    async with db_session.async_session_maker() as check_db:
                        stmt = select(AudioSegment).where(
                            AudioSegment.source_id == source.id,
                            AudioSegment.start_time == start_time,
                            AudioSegment.end_time == end_time,
                            AudioSegment.vector.is_not(None)  # 已有向量
                        )
                        result = await check_db.execute(stmt)
                        existing_segment = result.scalar_one_or_none()
                        if existing_segment:
                            logger.info(f"片段已存在且已有向量，跳过: {start_time:.2f}s - {end_time:.2f}s (ID: {existing_segment.id})")
                            # 仍计入成功计数
                            return True

                    # 2. 提取音频片段（使用原始文件）
                    segment_file_path = await audio_processing_service.extract_audio_segment(
                        source_file_path=str(audio_file_path),
                        start_time=start_time,
                        end_time=end_time,
                        output_format="mp3"
                    )

                    if not segment_file_path or not os.path.exists(segment_file_path):
                        logger.warning(f"片段提取失败: {start_time:.2f}s - {end_time:.2f}s")
                        return False

                    # 2. 转换音频为ASR优化格式（16000Hz, 单声道）
                    converted_segment_path = segments_dir / f"segment_{segment_index:04d}_converted.mp3"
                    conversion_success = await convert_audio_for_asr(
                        input_file_path=Path(segment_file_path),
                        output_file_path=converted_segment_path,
                        sample_rate=16000,
                        channels=1,
                        format="mp3"
                    )

                    if not conversion_success:
                        logger.warning(f"片段转换失败，使用原始片段")
                        converted_segment_path = Path(segment_file_path)

                    # 3. 上传片段到OSS
                    segment_filename = f"segment_{source.id}_{segment_index:04d}_{start_time:.1f}_{end_time:.1f}.mp3"
                    object_key, public_url = await upload_audio_file_to_oss(
                        local_file_path=str(converted_segment_path),
                        object_key=f"audio/segments/{source.id}/{segment_filename}",
                        metadata={
                            "source_id": source.id,
                            "start_time": start_time,
                            "end_time": end_time,
                            "segment_index": segment_index,
                            "created_at": datetime.utcnow().isoformat()
                        }
                    )

                    if not object_key or not public_url:
                        logger.warning("片段上传失败，跳过")
                        return False

                    logger.info(f"片段上传成功: {public_url}")

                    # 4. 阿里云ASR识别（使用转换后的音频）
                    transcription = await recognize_audio_file(
                        audio_file_path=str(converted_segment_path),
                        language="zh-CN",
                        sample_rate=16000,
                        format="mp3"
                    )

                    if not transcription:
                        logger.warning(f"ASR识别失败，使用备用文本")
                        transcription = f"音频片段 {start_time:.1f}s-{end_time:.1f}s (识别失败)"

                    # 文本去重
                    if transcription:
                        transcription = deduplicate_text(transcription)

                        # 检查清洗后文本长度，小于5个字则丢弃
                        if len(transcription) < 5:
                            logger.warning(f"音频片段文本过短({len(transcription)}<5)，丢弃")
                            return False

                    logger.info(f"ASR识别结果: {transcription[:100]}...")

                    # 5. 百炼向量化
                    vector = None
                    vector_dimension = None

                    if transcription:
                        vector = await get_text_vector(transcription, text_type="document")
                        vector_dimension = len(vector) if vector else None

                        if not vector:
                            logger.error("文本向量化失败")
                            # 继续处理，向量可以为空

                    # 6. 创建音频片段记录（使用新的数据库会话避免并发冲突）
                    async with db_session.async_session_maker() as segment_db:
                        async with segment_db.begin():
                            segment_id = str(uuid.uuid4())
                            segment = AudioSegment(
                                id=segment_id,
                                source_id=source.id,
                                user_id=None,
                                start_time=start_time,
                                end_time=end_time,
                                duration=end_time - start_time,
                                transcription=transcription,
                                language="zh-CN",
                                speaker=None,
                                emotion=None,
                                sentiment_score=None,
                                vector=vector,
                                vector_dimension=vector_dimension,
                                vector_updated_at=datetime.utcnow() if vector else None,
                                oss_key=object_key,
                                oss_url=public_url,
                                play_count=0,
                                favorite_count=0,
                                share_count=0,
                                tags=source.tags,
                                categories=[source.program_type] if source.program_type else None,
                                keywords=None,
                                review_status="approved",  # 自动导入的片段自动审核通过
                            )

                            segment_db.add(segment)
                            await segment_db.flush()
                            logger.info(f"创建音频片段记录: {segment_id}")

                        # 7. DashVector入库（在事务外执行，避免长时间占用连接）
                        if vector and transcription:
                            try:
                                logger.info("添加到向量索引...")
                                await add_audio_segment_to_index(segment_id, transcription)
                                logger.info(f"向量索引添加成功: {segment_id}")
                            except Exception as e:
                                logger.error(f"向量索引添加失败: {str(e)}")
                                # 继续处理，不因索引失败而中断

                    # 8. 清理临时文件
                    try:
                        os.remove(segment_file_path)
                        if converted_segment_path.exists() and converted_segment_path != Path(segment_file_path):
                            os.remove(converted_segment_path)
                    except:
                        pass

                    # 更新成功计数
                    return True

                except Exception as e:
                    logger.error(f"处理片段 {segment_index+1} 失败: {e}", exc_info=True)
                    return False
                finally:
                    # 更新进度（原子操作）
                    processed_segments += 1
                    # 实时更新处理进度到源记录
                    try:
                        async with db_session.async_session_maker() as progress_db:
                            progress_source = await progress_db.get(AudioSource, source.id)
                            if progress_source:
                                progress_source.processing_progress = 0.3 + (processed_segments / total_segments) * 0.7
                                await progress_db.commit()
                    except Exception as e:
                        logger.warning(f"更新进度失败: {str(e)}")

        # 3. 并发处理所有片段
        logger.info(f"开始并发处理 {total_segments} 个片段，最大并发数: {SEGMENT_CONCURRENCY_LIMIT}")
        tasks = [
            process_single_segment(i, start_time, end_time)
            for i, (start_time, end_time) in enumerate(segments_ranges)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计成功数，处理异常结果
        successful_segments = 0
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"片段处理异常: {str(r)}")
            elif r is True:
                successful_segments += 1

        # 4. 更新音频源状态
        async with db_session.async_session_maker() as final_db:
            final_source = await final_db.get(AudioSource, source.id)
            if final_source:
                if successful_segments > 0:
                    final_source.processing_status = "completed"
                    final_source.processing_progress = 1.0
                    logger.info(f"音频处理完成，成功创建 {successful_segments}/{total_segments} 个片段")
                else:
                    final_source.processing_status = "failed"
                    final_source.error_message = "未成功创建任何片段"
                    logger.error("音频处理失败，未创建任何片段")
                await final_db.commit()

        # 5. 清理临时目录
        try:
            import shutil
            if segments_dir.exists():
                shutil.rmtree(segments_dir)
        except:
            pass

        return successful_segments, total_segments

    except Exception as e:
        logger.error(f"处理音频片段失败: {str(e)}", exc_info=True)
        async with db_session.async_session_maker() as error_db:
            error_source = await error_db.get(AudioSource, source.id)
            if error_source:
                error_source.processing_status = "failed"
                error_source.error_message = str(e)
                await error_db.commit()
        return 0, 0


async def process_single_audio_file(
    db: AsyncSession,
    audio_file_path: Path,
    dry_run: bool = False
) -> Dict[str, Any]:
    """处理单个音频文件"""
    result = {
        "file": str(audio_file_path),
        "success": False,
        "source_id": None,
        "segments_created": 0,
        "segments_total": 0,
        "error": None
    }

    try:
        # 1. 检查文件是否存在
        if not audio_file_path.exists():
            result["error"] = "文件不存在"
            return result

        # 2. 计算文件哈希
        file_hash = calculate_file_hash(audio_file_path)

        # 3. 检查是否已处理
        existing_source = await check_existing_source(db, audio_file_path.name, file_hash)
        if existing_source:
            result["success"] = True
            result["source_id"] = existing_source.id
            result["segments_created"] = 0
            result["segments_total"] = 0
            result["message"] = "文件已处理，跳过"
            return result

        if dry_run:
            result["success"] = True
            result["message"] = "Dry run模式，跳过实际处理"
            return result

        # 4. 创建音频源记录
        source = await create_audio_source(db, audio_file_path, file_hash)
        if not source:
            result["error"] = "创建音频源记录失败"
            return result

        # 5. 上传音频源到OSS
        upload_success = await upload_source_to_oss(db, source, audio_file_path)
        if not upload_success:
            result["error"] = "音频源上传失败"
            return result

        # 6. 转换音频为ASR优化格式
        converted_audio_path = None
        temp_converted_path = backend_dir / "storage" / "temp" / f"{source.id}_converted.mp3"
        temp_converted_path.parent.mkdir(parents=True, exist_ok=True)

        conversion_success = await convert_audio_for_asr(
            input_file_path=audio_file_path,
            output_file_path=temp_converted_path,
            sample_rate=16000,
            channels=1,
            format="mp3"
        )

        if conversion_success:
            converted_audio_path = temp_converted_path
            logger.info(f"音频转换成功，使用转换后的文件进行分割")
        else:
            logger.warning(f"音频转换失败，使用原始文件进行分割")

        # 7. 处理音频片段
        segments_created, segments_total = await process_audio_segments(
            db, source, audio_file_path, converted_audio_path
        )

        # 清理临时文件
        if converted_audio_path and converted_audio_path.exists():
            try:
                os.remove(converted_audio_path)
            except:
                pass

        # 8. 返回结果
        result["success"] = True
        result["source_id"] = source.id
        result["segments_created"] = segments_created
        result["segments_total"] = segments_total

        logger.info(f"文件处理完成: {audio_file_path.name}, 创建 {segments_created} 个片段")

    except Exception as e:
        logger.error(f"处理文件失败 {audio_file_path}: {str(e)}", exc_info=True)
        result["error"] = str(e)

    return result


async def get_statistics(db: AsyncSession) -> Dict[str, Any]:
    """获取数据库统计信息"""
    try:
        # 音频源数量
        result = await db.execute(select(func.count()).select_from(AudioSource))
        total_sources = result.scalar()

        # 音频片段数量
        result = await db.execute(select(func.count()).select_from(AudioSegment))
        total_segments = result.scalar()

        # 已审核的片段数量
        result = await db.execute(
            select(func.count()).select_from(AudioSegment).where(AudioSegment.review_status == "approved")
        )
        approved_segments = result.scalar()

        return {
            "total_sources": total_sources or 0,
            "total_segments": total_segments or 0,
            "approved_segments": approved_segments or 0
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return {}


async def setup_services():
    """初始化AI和存储服务"""
    logger.info("初始化AI和存储服务...")

    # 初始化ASR服务
    try:
        await init_asr_service()
        logger.info("ASR服务初始化完成")
    except Exception as e:
        logger.warning(f"ASR服务初始化失败: {str(e)}")

    # 初始化NLP服务
    try:
        await init_nlp_service()
        logger.info("NLP服务初始化完成")
    except Exception as e:
        logger.warning(f"NLP服务初始化失败: {str(e)}")

    # 初始化存储服务
    try:
        await init_storage_service()
        logger.info("存储服务初始化完成")
    except Exception as e:
        logger.warning(f"存储服务初始化失败: {str(e)}")

    # 初始化向量索引
    try:
        await init_vector_index()
        logger.info("向量索引初始化完成")
    except Exception as e:
        logger.warning(f"向量索引初始化失败: {str(e)}")

    logger.info("所有服务初始化完成")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="批量音频入库脚本")
    parser.add_argument(
        "directory",
        nargs="?",
        default="storage/raw_media",
        help="音频文件目录（默认: storage/raw_media）"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=2,
        help="最大并发处理文件数（默认: 2）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干运行模式，只扫描文件不实际处理"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="跳过已处理的文件（默认: True）"
    )

    args = parser.parse_args()

    # 解析目录路径
    scan_directory = Path(args.directory).absolute()

    logger.info("=== 批量音频入库开始 ===")
    logger.info(f"扫描目录: {scan_directory}")
    logger.info(f"最大并发数: {args.max_concurrent}")
    logger.info(f"干运行模式: {args.dry_run}")
    logger.info(f"跳过已处理文件: {args.skip_existing}")

    try:
        # 初始化数据库
        logger.info("初始化数据库...")
        await init_db()

        # 确保表存在
        async with db_session.async_session_maker() as session:
            async with session.bind.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("数据库表已创建/验证")

        # 初始化服务
        await setup_services()

        # 扫描音频文件
        audio_files = scan_audio_files(scan_directory)

        if not audio_files:
            logger.error(f"在目录 {scan_directory} 中未找到音频文件")
            return 1

        # 处理前统计
        async with db_session.async_session_maker() as db:
            stats_before = await get_statistics(db)
            logger.info(f"处理前统计: {stats_before}")

        # 并发处理文件
        semaphore = asyncio.Semaphore(args.max_concurrent)
        processing_results = []

        async def process_with_semaphore(file_path: Path) -> Dict[str, Any]:
            async with semaphore:
                async with db_session.async_session_maker() as db:
                    return await process_single_audio_file(db, file_path, args.dry_run)

        tasks = [process_with_semaphore(file_path) for file_path in audio_files]
        processing_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        successful_files = 0
        skipped_files = 0
        failed_files = 0
        total_segments_created = 0
        total_segments_total = 0

        for i, result in enumerate(processing_results):
            if isinstance(result, Exception):
                logger.error(f"文件处理异常 {audio_files[i]}: {str(result)}")
                failed_files += 1
                continue

            if result.get("success"):
                if result.get("message") == "文件已处理，跳过":
                    skipped_files += 1
                else:
                    successful_files += 1
                    total_segments_created += result.get("segments_created", 0)
                    total_segments_total += result.get("segments_total", 0)
            else:
                failed_files += 1
                logger.error(f"文件处理失败 {audio_files[i]}: {result.get('error')}")

        # 处理后统计
        async with db_session.async_session_maker() as db:
            stats_after = await get_statistics(db)

        # 输出总结
        logger.info("=== 处理总结 ===")
        logger.info(f"扫描文件总数: {len(audio_files)}")
        logger.info(f"成功处理文件: {successful_files}")
        logger.info(f"跳过已处理文件: {skipped_files}")
        logger.info(f"处理失败文件: {failed_files}")
        logger.info(f"创建音频片段总数: {total_segments_created} (共尝试 {total_segments_total} 个片段)")

        if not args.dry_run:
            logger.info(f"数据库统计:")
            logger.info(f"  - 音频源总数: {stats_after.get('total_sources', 0)} (新增: {stats_after.get('total_sources', 0) - stats_before.get('total_sources', 0)})")
            logger.info(f"  - 音频片段总数: {stats_after.get('total_segments', 0)} (新增: {stats_after.get('total_segments', 0) - stats_before.get('total_segments', 0)})")
            logger.info(f"  - 已审核片段数: {stats_after.get('approved_segments', 0)}")

        # 保存处理结果到文件
        result_file = backend_dir / "storage" / f"ingestion_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)

        summary = {
            "timestamp": datetime.now().isoformat(),
            "scan_directory": str(scan_directory),
            "total_files_scanned": len(audio_files),
            "successful_files": successful_files,
            "skipped_files": skipped_files,
            "failed_files": failed_files,
            "segments_created": total_segments_created,
            "segments_total": total_segments_total,
            "stats_before": stats_before,
            "stats_after": stats_after,
            "dry_run": args.dry_run,
            "results": processing_results
        }

        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"详细结果已保存到: {result_file}")

        if failed_files > 0:
            logger.warning(f"有 {failed_files} 个文件处理失败，请检查日志")
            return 1

        logger.info("=== 批量音频入库完成 ===")
        return 0

    except Exception as e:
        logger.error(f"批量音频入库失败: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)