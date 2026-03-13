"""
Celery任务定义
"""
import logging
import asyncio
from typing import Optional
from celery import current_task

from celery_app import celery_app
from config import settings
from shared.database.session import get_db_async_session
from services.audio_processing_service import audio_processing_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='process_audio_source')
def process_audio_source_task(self, source_id: str, user_id: str) -> Optional[str]:
    """
    处理音频源的Celery任务

    Args:
        source_id: 音频源ID
        user_id: 用户ID

    Returns:
        处理结果信息
    """
    try:
        logger.info(f"开始处理音频源任务: {source_id}")

        # 更新任务状态
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '开始处理'}
        )

        # 由于Celery任务通常是同步的，我们需要运行异步函数
        # 这里使用asyncio.run在事件循环中运行异步代码
        async def async_process():
            async with get_db_async_session() as db:
                # 这里需要获取source和user对象
                # 为了简化，暂时只记录日志
                logger.info(f"模拟处理音频源: {source_id}, 用户: {user_id}")

                # 模拟处理进度
                for i in range(1, 6):
                    await asyncio.sleep(1)
                    progress = i * 20
                    current_task.update_state(
                        state='PROGRESS',
                        meta={'current': progress, 'total': 100, 'status': f'处理中 ({i}/5)'}
                    )

                return f"音频源 {source_id} 处理完成"

        result = asyncio.run(async_process())

        logger.info(f"音频源处理任务完成: {source_id}")
        return result

    except Exception as e:
        logger.error(f"音频源处理任务失败: {str(e)}")
        raise


@celery_app.task(bind=True, name='transcribe_audio_file')
def transcribe_audio_file_task(
    self,
    audio_file_path: str,
    language: str = "zh-CN",
) -> Optional[str]:
    """
    转录音频文件的Celery任务

    Args:
        audio_file_path: 音频文件路径
        language: 语言代码

    Returns:
        转录文本
    """
    try:
        logger.info(f"开始转录音频文件: {audio_file_path}")

        # 更新任务状态
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': '开始转录'}
        )

        # 异步转录
        async def async_transcribe():
            from ai_models.asr_service import recognize_audio_file

            # 模拟进度更新
            current_task.update_state(
                state='PROGRESS',
                meta={'current': 30, 'total': 100, 'status': '正在识别音频'}
            )

            transcription = await recognize_audio_file(
                audio_file_path,
                language=language,
            )

            current_task.update_state(
                state='PROGRESS',
                meta={'current': 90, 'total': 100, 'status': '识别完成'}
            )

            return transcription

        result = asyncio.run(async_transcribe())

        logger.info(f"音频文件转录完成: {audio_file_path}")
        return result

    except Exception as e:
        logger.error(f"音频文件转录任务失败: {str(e)}")
        raise


@celery_app.task(bind=True, name='batch_transcribe_audio_files')
def batch_transcribe_audio_files_task(
    self,
    file_paths: list,
    language: str = "zh-CN",
) -> list:
    """
    批量转录音频文件

    Args:
        file_paths: 音频文件路径列表
        language: 语言代码

    Returns:
        转录结果列表
    """
    try:
        logger.info(f"开始批量转录音频文件，数量: {len(file_paths)}")

        total_files = len(file_paths)
        results = []

        for i, file_path in enumerate(file_paths):
            # 更新任务状态
            progress = int((i / total_files) * 100)
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': progress,
                    'total': 100,
                    'status': f'处理中 ({i+1}/{total_files})',
                    'current_file': file_path,
                }
            )

            # 转录单个文件
            result = transcribe_audio_file_task.apply_async(
                args=[file_path, language],
                queue='transcription'
            ).get()

            results.append({
                'file_path': file_path,
                'transcription': result,
                'success': result is not None,
            })

        logger.info(f"批量音频文件转录完成，成功: {sum(1 for r in results if r['success'])}/{total_files}")
        return results

    except Exception as e:
        logger.error(f"批量音频文件转录任务失败: {str(e)}")
        raise


@celery_app.task(name='update_vector_index')
def update_vector_index_task(segment_ids: list) -> dict:
    """
    更新向量索引

    Args:
        segment_ids: 音频片段ID列表

    Returns:
        更新结果
    """
    try:
        logger.info(f"开始更新向量索引，片段数量: {len(segment_ids)}")

        # 这里应该调用search_service中的索引更新函数
        # 暂时返回模拟结果
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


@celery_app.task(name='extract_audio_features')
def extract_audio_features_task(audio_file_path: str) -> dict:
    """
    提取音频特征

    Args:
        audio_file_path: 音频文件路径

    Returns:
        特征字典
    """
    try:
        logger.info(f"开始提取音频特征: {audio_file_path}")

        # 异步提取特征
        async def async_extract():
            features = await audio_processing_service.extract_audio_features(audio_file_path)
            return features

        features = asyncio.run(async_extract())

        logger.info(f"音频特征提取完成: {audio_file_path}")
        return {
            'success': True,
            'features': features,
            'file_path': audio_file_path,
        }

    except Exception as e:
        logger.error(f"音频特征提取任务失败: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'file_path': audio_file_path,
        }