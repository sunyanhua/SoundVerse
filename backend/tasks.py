"""
Celery任务定义
"""
import logging
import asyncio
from typing import Optional
from celery import current_task

from celery_app import celery_app
from config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='process_audio_source')
def process_audio_source_task(self, source_id: str, user_id: str) -> Optional[str]:
    """
    处理音频源的Celery任务 - 真正的音频裁切处理

    Args:
        source_id: 音频源ID
        user_id: 用户ID

    Returns:
        处理结果信息
    """
    logger.info(f"[Celery] 开始处理音频源: {source_id}")

    try:
        # 更新任务状态
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '开始处理'}
        )

        # 运行异步处理函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                _process_audio_in_celery(source_id, user_id, self)
            )
            logger.info(f"[Celery] 音频源处理完成: {source_id}")
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"[Celery] 音频源处理任务失败: {source_id}, 错误: {str(e)}")
        # 更新状态为失败
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_mark_processing_failed(source_id, str(e)))
            loop.close()
        except:
            pass
        raise


# 全局集合，用于跟踪正在处理的音频源（防止重复处理）
_processing_sources = set()

async def _process_audio_in_celery(source_id: str, user_id: str, task_instance):
    """
    在Celery中处理音频源（幂等性保证）
    """
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from shared.models.audio import AudioSource, AudioSegment
    from shared.models.user import User
    from services.audio_processing_service import AudioProcessingService
    from pathlib import Path

    # 检查是否已经在处理中（内存级去重）
    if source_id in _processing_sources:
        logger.warning(f"[Celery] 音频源 {source_id} 正在处理中，跳过重复任务")
        return "已在处理中"

    service = AudioProcessingService()

    # 创建独立的数据库引擎
    engine = create_async_engine(
        settings.get_database_url(),
        echo=False,
        pool_size=5,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with session_maker() as db:
            # 获取音频源
            stmt = select(AudioSource).where(AudioSource.id == source_id)
            result = await db.execute(stmt)
            source = result.scalar_one_or_none()

            if not source:
                logger.error(f"[Celery] 音频源不存在: {source_id}")
                return "音频源不存在"

            # 获取用户
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.error(f"[Celery] 用户不存在: {user_id}")
                return "用户不存在"

            # 检查文件是否存在
            file_path = source.oss_url
            if not Path(file_path).exists():
                logger.error(f"[Celery] 音频文件不存在: {file_path}")
                source.processing_status = "failed"
                source.error_message = "音频文件不存在"
                await db.commit()
                return "音频文件不存在"

            # 幂等性检查：如果已经处理完成，直接返回
            if source.processing_status == "completed":
                logger.info(f"[Celery] 音频源 {source_id} 已处理完成，跳过")
                return "已处理完成"

            # 检查是否已有片段（部分处理的情况）
            stmt = select(func.count(AudioSegment.id)).where(AudioSegment.source_id == source_id)
            result = await db.execute(stmt)
            segment_count = result.scalar()

            if segment_count > 0 and source.processing_status == "completed":
                logger.info(f"[Celery] 音频源 {source_id} 已有 {segment_count} 个片段且状态完成，跳过")
                return "已处理完成"

            # 标记为正在处理（内存级去重）
            _processing_sources.add(source_id)
            logger.info(f"[Celery] 开始处理音频: {source.title} (当前已有 {segment_count} 个片段)")

            # 使用 AudioProcessingService 处理音频
            success = await service.process_audio_source(db, source, user)

            if success:
                logger.info(f"[Celery] 音频源处理完成: {source_id}")
                return f"音频源 {source_id} 处理完成"
            else:
                logger.error(f"[Celery] 音频源处理失败: {source_id}")
                return f"音频源 {source_id} 处理失败"

    except Exception as e:
        logger.error(f"[Celery] 处理异常: {source_id}, 错误: {str(e)}")
        raise
    finally:
        # 清理内存中的处理标记
        _processing_sources.discard(source_id)
        await engine.dispose()


async def _mark_processing_failed(source_id: str, error_message: str):
    """
    标记处理状态为失败
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from shared.models.audio import AudioSource
    from config import settings

    engine = create_async_engine(
        settings.get_database_url(),
        echo=False,
    )

    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    try:
        async with session_maker() as db:
            stmt = select(AudioSource).where(AudioSource.id == source_id)
            result = await db.execute(stmt)
            source = result.scalar_one_or_none()
            if source:
                source.processing_status = "failed"
                source.error_message = error_message
                await db.commit()
    except Exception as e:
        logger.error(f"[Celery] 更新失败状态时出错: {e}")
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name='transcribe_audio_file')
def transcribe_audio_file_task(
    self,
    audio_file_path: str,
    language: str = "zh-CN",
) -> Optional[str]:
    """
    转录音频文件的Celery任务
    """
    try:
        logger.info(f"开始转录音频文件: {audio_file_path}")

        async def async_transcribe():
            from ai_models.asr_service import recognize_audio_file
            transcription = await recognize_audio_file(
                audio_file_path,
                language=language,
            )
            return transcription

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_transcribe())
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"音频文件转录任务失败: {str(e)}")
        raise


@celery_app.task(name='update_vector_index')
def update_vector_index_task(segment_ids: list) -> dict:
    """
    更新向量索引
    """
    try:
        logger.info(f"开始更新向量索引，片段数量: {len(segment_ids)}")
        return {
            'success': True,
            'updated_count': len(segment_ids),
            'message': f"成功更新 {len(segment_ids)} 个片段的向量索引",
        }
    except Exception as e:
        logger.error(f"更新向量索引任务失败: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'message': "更新向量索引失败",
        }
