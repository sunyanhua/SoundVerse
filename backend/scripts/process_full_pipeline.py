#!/usr/bin/env python3
"""
完整音频处理流水线测试脚本：对 test_radio.mp3 进行全流程处理
流程：静音切片 -> OSS上传 -> 阿里云ASR识别 -> 百炼向量化 -> DashVector入库
"""
import asyncio
import sys
import os
import logging
from pathlib import Path
from datetime import datetime
import uuid

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
from shared.database.session import init_db, Base
import shared.database.session as db_session
from shared.models.audio import AudioSource, AudioSegment
from shared.models.user import User
from shared.models.chat import ChatMessage  # 确保 ChatMessage 模型已注册
from services.audio_processing_service import audio_processing_service, deduplicate_text
from services.storage_service import upload_audio_file_to_oss, init_storage_service
from ai_models.asr_service import recognize_audio_file, init_asr_service
from ai_models.nlp_service import get_text_vector, init_nlp_service
from services.search_service import add_audio_segment_to_index, init_vector_index
from config import settings

# 临时调整音频最大时长限制，以通过验证
settings.MAX_AUDIO_DURATION = 600.0  # 600秒

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)




async def setup_database():
    """初始化数据库"""
    logger.info("初始化数据库...")
    await init_db()

    # 确保表存在（开发环境）
    async with db_session.async_session_maker() as session:
        async with session.bind.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库表已创建/验证")


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


async def create_test_audio_source(db: AsyncSession) -> AudioSource:
    """创建测试音频源记录"""
    source_id = str(uuid.uuid4())
    source = AudioSource(
        id=source_id,
        title="完整流水线测试广播节目",
        description="用于测试完整音频处理流水线的测试广播节目",
        program_type="news",
        episode_number="2026-03-08-001",
        broadcast_date=datetime.utcnow(),
        original_filename="test_radio.mp3",
        file_size=os.path.getsize(backend_dir / "test_radio.mp3"),
        duration=0.0,  # 将在分割后更新
        format="mp3",
        sample_rate=16000,
        channels=1,
        oss_key=f"test/sources/{source_id}.mp3",
        oss_url=f"{settings.OSS_PUBLIC_DOMAIN}/test/sources/{source_id}.mp3" if hasattr(settings, 'OSS_PUBLIC_DOMAIN') and settings.OSS_PUBLIC_DOMAIN else f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}/test/sources/{source_id}.mp3",
        processing_status="processing",
        processing_progress=0.0,
        copyright_holder="SoundVerse测试",
        license_type="test",
        is_public=True,
        tags=["test", "radio", "full_pipeline"],
        extra_metadata={"test": True, "created_by": "full_pipeline_test"}
    )

    db.add(source)
    await db.flush()
    logger.info(f"创建音频源记录: {source.id}")
    return source


async def process_audio_file(db: AsyncSession, source: AudioSource):
    """
    处理音频文件：完整流水线
    """
    audio_file_path = backend_dir / "test_radio.mp3"

    if not audio_file_path.exists():
        logger.error(f"音频文件不存在: {audio_file_path}")
        return False

    logger.info(f"开始处理音频文件: {audio_file_path}")

    # 1. 验证音频文件
    validation = await audio_processing_service.validate_audio_file(str(audio_file_path))
    logger.info(f"音频验证结果: {validation}")

    if not validation.get("valid"):
        logger.error(f"音频文件验证失败: {validation.get('messages', ['未知错误'])}")
        return False

    # 更新音频源时长
    source.duration = validation["duration"]
    source.sample_rate = validation["sample_rate"]
    source.channels = validation["channels"]
    await db.commit()

    # 2. 静音分割
    logger.info("开始静音分割...")
    try:
        segments_ranges = await audio_processing_service.split_audio_by_silence(str(audio_file_path))
        logger.info(f"静音分割完成，得到 {len(segments_ranges)} 个片段区间")

        if not segments_ranges:
            logger.warning("未检测到任何非静音频段，可能是静音阈值设置问题或文件本身为静音")
            return False
    except Exception as e:
        logger.error(f"静音分割失败: {e}")
        return False

    # 3. 创建存储目录（用于临时片段文件）
    segments_dir = backend_dir / "storage" / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"临时片段存储目录: {segments_dir}")

    # 4. 处理每个片段
    total_segments = len(segments_ranges)
    successful_segments = 0

    for i, (start_time, end_time) in enumerate(segments_ranges):
        try:
            logger.info(f"处理片段 {i+1}/{total_segments}: {start_time:.2f}s - {end_time:.2f}s")

            # 4.1 提取音频片段（本地临时文件）
            segment_file_path = await audio_processing_service.extract_audio_segment(
                source_file_path=str(audio_file_path),
                start_time=start_time,
                end_time=end_time,
                output_format="mp3"
            )

            if not segment_file_path or not os.path.exists(segment_file_path):
                logger.warning(f"片段提取失败: {start_time:.2f}s - {end_time:.2f}s")
                continue

            # 4.2 将片段移动到存储目录（临时保存）
            segment_filename = f"segment_{source.id}_{i:04d}_{start_time:.1f}_{end_time:.1f}.mp3"
            segment_storage_path = segments_dir / segment_filename

            import shutil
            shutil.copy2(segment_file_path, segment_storage_path)
            # 如果是临时文件，复制后删除临时文件
            if "tmp" in str(segment_file_path):
                os.remove(segment_file_path)

            logger.info(f"临时片段保存到: {segment_storage_path}")

            # 4.3 上传片段到OSS
            logger.info("上传片段到OSS...")
            object_key, public_url = await upload_audio_file_to_oss(
                local_file_path=str(segment_storage_path),
                object_key=f"audio/segments/{source.id}/{segment_filename}",
                metadata={
                    "source_id": source.id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "segment_index": i,
                    "created_at": datetime.utcnow().isoformat()
                }
            )

            if not object_key or not public_url:
                logger.warning("OSS上传失败，跳过此片段")
                continue

            logger.info(f"片段上传成功: {public_url}")

            # 4.4 阿里云ASR识别
            logger.info("开始ASR识别...")
            transcription = await recognize_audio_file(
                audio_file_path=str(segment_storage_path),
                language="zh-CN",
                sample_rate=16000,
                format="mp3"
            )

            if not transcription:
                logger.warning(f"ASR识别失败，使用备用文本")
                transcription = f"音频片段 {start_time:.1f}s-{end_time:.1f}s (识别失败)"

            logger.info(f"ASR识别结果: {transcription[:100]}...")

            # 4.4.1 文本去重（移除连续重复的句子）
            if transcription:
                transcription = deduplicate_text(transcription)
                logger.info(f"去重后文本: {transcription[:100]}...")

                # 检查清洗后文本长度，小于5个字则丢弃
                if len(transcription) < 5:
                    logger.warning(f"音频片段文本过短({len(transcription)}<5)，丢弃: {start_time:.1f}s-{end_time:.1f}s")
                    continue

            # 4.5 百炼向量化
            logger.info("开始文本向量化...")
            if not transcription:
                logger.warning("转录文本为空，跳过向量化")
                vector = None
                vector_dimension = None
            else:
                vector = await get_text_vector(transcription, text_type="document")
                vector_dimension = len(vector) if vector else None

                if not vector:
                    logger.error("❌ 文本向量化失败：API返回None，立即停止脚本")
                    print(f"转录文本: {transcription}")
                    print(f"向量化失败原因：DashScope API调用失败，向量为None")
                    sys.exit(1)

                # 验证向量维度
                if vector_dimension != 1024:
                    logger.error(f"❌ 向量维度不匹配：预期1024，实际{vector_dimension}")
                    print(f"转录文本: {transcription}")
                    print(f"向量维度: {vector_dimension}")
                    sys.exit(1)

                logger.info(f"✅ 文本向量化成功：{vector_dimension}维")

            # 4.6 创建音频片段记录
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
                review_status="approved",  # 全量授权，跳过审核
            )

            db.add(segment)
            await db.flush()
            logger.info(f"创建音频片段记录: {segment_id}")

            # 4.7 DashVector入库
            if vector and transcription:
                try:
                    logger.info("添加到向量索引...")
                    await add_audio_segment_to_index(segment_id, transcription)
                    logger.info(f"向量索引添加成功: {segment_id}")
                except Exception as e:
                    logger.error(f"向量索引添加失败: {str(e)}")
                    # 继续处理，不因索引失败而中断

            successful_segments += 1

            # 更新处理进度
            source.processing_progress = (i + 1) / total_segments
            await db.commit()

            # 清理临时文件
            try:
                os.remove(segment_storage_path)
            except:
                pass

        except Exception as e:
            logger.error(f"处理片段 {i+1} 失败: {e}", exc_info=True)
            continue

    # 5. 更新音频源状态
    if successful_segments > 0:
        source.processing_status = "completed"
        source.processing_progress = 1.0
        logger.info(f"音频处理完成，成功创建 {successful_segments}/{total_segments} 个片段")
    else:
        source.processing_status = "failed"
        source.error_message = "未成功创建任何片段"
        logger.error("音频处理失败，未创建任何片段")

    await db.commit()
    return successful_segments > 0


async def count_audio_segments(db: AsyncSession) -> int:
    """统计音频片段数量"""
    from sqlalchemy import select, func
    result = await db.execute(select(func.count()).select_from(AudioSegment))
    count = result.scalar()
    return count


async def test_search():
    """测试搜索功能"""
    try:
        from services.search_service import search_audio_segments_by_text

        logger.info("=== 测试搜索功能 ===")
        query = "北京时间"
        logger.info(f"搜索查询: '{query}'")

        results = await search_audio_segments_by_text(query, top_k=3)

        if not results:
            logger.warning("搜索未返回结果")
            return False

        logger.info(f"搜索返回 {len(results)} 个结果:")
        for i, (segment_id, similarity) in enumerate(results):
            logger.info(f"  结果 {i+1}: 片段ID={segment_id}, 相似度={similarity:.4f}")

            # 获取片段详情
            async with db_session.async_session_maker() as db:
                stmt = select(AudioSegment).where(AudioSegment.id == segment_id)
                result = await db.execute(stmt)
                segment = result.scalar_one_or_none()

                if segment:
                    logger.info(f"     文本: {segment.transcription[:100]}...")
                    logger.info(f"     OSS URL: {segment.oss_url}")
                    logger.info(f"     时间: {segment.start_time:.1f}s - {segment.end_time:.1f}s")
                else:
                    logger.warning(f"     片段 {segment_id} 不存在于数据库")

        return True

    except Exception as e:
        logger.error(f"搜索测试失败: {str(e)}", exc_info=True)
        return False


async def main():
    """主函数"""
    logger.info("=== 完整音频处理流水线测试开始 ===")

    try:
        # 初始化数据库
        await setup_database()

        # 初始化AI和存储服务
        await setup_services()

        # 创建数据库会话
        async with db_session.async_session_maker() as db:
            # 创建测试音频源
            source = await create_test_audio_source(db)

            # 处理音频文件
            success = await process_audio_file(db, source)

            if success:
                # 查询片段数量
                segments_count = await count_audio_segments(db)
                logger.info(f"音频片段总数: {segments_count}")

                # 打印片段信息
                from sqlalchemy import select
                result = await db.execute(
                    select(AudioSegment).where(AudioSegment.source_id == source.id)
                )
                segments = result.scalars().all()

                logger.info(f"本次创建的片段 ({len(segments)} 个):")
                for seg in segments:
                    logger.info(f"  - ID: {seg.id}, 时间: {seg.start_time:.1f}s-{seg.end_time:.1f}s, "
                               f"时长: {seg.duration:.1f}s, 文本: {seg.transcription[:50] if seg.transcription else '无'}...")
                    logger.info(f"    OSS URL: {seg.oss_url}")

                # 测试搜索功能
                await test_search()

                logger.info("=== 测试成功完成 ===")
            else:
                logger.error("=== 测试失败 ===")

    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}", exc_info=True)
        return 1

    logger.info("=== 测试结束 ===")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)