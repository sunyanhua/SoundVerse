#!/usr/bin/env python3
"""
音频片段数据清洗与重新向量化脚本
功能：
1. 清理ASR文字：删除转录文本中连续重复的句子
2. 重新向量化：清洗后调用百炼接口重新生成1024维向量
3. 更新数据库和DashVector索引
"""

import asyncio
import sys
import os
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 使用Docker容器内的默认MySQL连接
import os
if os.environ.get("DATABASE_URL") is None:
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import shared.database.session as db_session
from shared.database.session import init_db, Base
from shared.models.audio import AudioSegment
from shared.models.user import User  # 确保User模型被注册
from ai_models.nlp_service import get_text_vector
from services.search_service import add_audio_segment_to_index, init_vector_index
from config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def deduplicate_text(text: str, min_sentence_length: int = 3) -> str:
    """
    移除转录文本中连续重复的句子

    Args:
        text: 原始转录文本
        min_sentence_length: 最小句子长度（字符数），短于此长度的句子不进行去重

    Returns:
        去重后的文本
    """
    if not text:
        return text

    # 中文句子分隔符：。！？；，、\n
    sentence_delimiters = r'[。！？；，、\n]+'
    sentences = re.split(sentence_delimiters, text)

    # 过滤空句子和短句子
    sentences = [s.strip() for s in sentences if s.strip()]

    # 移除连续重复的句子
    deduped_sentences = []
    prev_sentence = None
    repeat_count = 0

    for sentence in sentences:
        # 如果句子太短，保留（可能是语气词等）
        if len(sentence) < min_sentence_length:
            deduped_sentences.append(sentence)
            prev_sentence = sentence
            continue

        # 检查是否与上一句相同
        if sentence == prev_sentence:
            repeat_count += 1
            # 如果连续重复超过1次（即出现3次相同句子），跳过后续重复
            if repeat_count > 1:
                continue
            else:
                deduped_sentences.append(sentence)
        else:
            # 新句子
            deduped_sentences.append(sentence)
            prev_sentence = sentence
            repeat_count = 0

    # 重新组合句子，使用句号连接
    result = '。'.join(deduped_sentences)
    if result and not result.endswith('。'):
        result += '。'

    logger.debug(f"去重前: {text[:200]}...")
    logger.debug(f"去重后: {result[:200]}...")
    logger.info(f"句子去重: {len(sentences)} -> {len(deduped_sentences)} 句")

    return result


async def analyze_duplicate_rate(segments: List[AudioSegment]) -> dict:
    """
    分析重复率统计

    Args:
        segments: 音频片段列表

    Returns:
        重复率统计信息
    """
    total_sentences = 0
    duplicate_sentences = 0

    for segment in segments:
        if not segment.transcription:
            continue

        # 分割句子
        sentence_delimiters = r'[。！？；，、\n]+'
        sentences = re.split(sentence_delimiters, segment.transcription)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 2:
            continue

        total_sentences += len(sentences)

        # 统计连续重复的句子
        prev_sentence = None
        for i, sentence in enumerate(sentences):
            if i > 0 and sentence == prev_sentence and len(sentence) >= 3:
                duplicate_sentences += 1
            prev_sentence = sentence

    duplicate_rate = duplicate_sentences / total_sentences if total_sentences > 0 else 0

    return {
        "total_segments": len(segments),
        "total_sentences": total_sentences,
        "duplicate_sentences": duplicate_sentences,
        "duplicate_rate": duplicate_rate,
        "duplicate_rate_percent": duplicate_rate * 100
    }


async def refine_segment(db: AsyncSession, segment: AudioSegment) -> bool:
    """
    清洗单个音频片段并重新向量化

    Args:
        db: 数据库会话
        segment: 音频片段

    Returns:
        是否成功
    """
    try:
        original_text = segment.transcription or ""

        # 1. 清洗文本（去重）
        cleaned_text = deduplicate_text(original_text)

        # 如果文本没有变化，跳过
        if cleaned_text == original_text:
            logger.debug(f"片段 {segment.id} 文本无重复，跳过")
            return False

        logger.info(f"片段 {segment.id}: 文本去重完成")
        logger.debug(f"  原始: {original_text[:100]}...")
        logger.debug(f"  清洗后: {cleaned_text[:100]}...")

        # 2. 重新向量化
        logger.info(f"片段 {segment.id}: 重新向量化...")
        new_vector = await get_text_vector(cleaned_text, text_type="document")

        if not new_vector:
            logger.warning(f"片段 {segment.id}: 向量化失败，跳过")
            return False

        # 3. 更新数据库
        segment.transcription = cleaned_text
        segment.vector = new_vector
        segment.vector_dimension = len(new_vector)
        segment.vector_updated_at = datetime.utcnow()

        # 4. 更新DashVector索引
        logger.info(f"片段 {segment.id}: 更新向量索引...")
        try:
            # 先尝试删除旧的向量（如果存在）
            from services.search_service import search_service
            # 这里需要调用DashVector的删除API
            # 暂时跳过删除，直接upsert（DashVector支持更新）
            pass
        except Exception as e:
            logger.warning(f"片段 {segment.id}: 清理旧向量失败: {str(e)}")

        # 添加到索引（会更新现有文档）
        await add_audio_segment_to_index(segment.id, cleaned_text)

        logger.info(f"片段 {segment.id}: 清洗完成，文本长度 {len(original_text)} -> {len(cleaned_text)}")
        return True

    except Exception as e:
        logger.error(f"片段 {segment.id} 清洗失败: {str(e)}", exc_info=True)
        return False


async def refine_all_segments():
    """
    清洗所有音频片段
    """
    logger.info("=== 开始音频片段数据清洗 ===")

    try:
        # 初始化数据库连接
        await init_services()

        # 创建数据库会话
        async with db_session.async_session_maker() as db:
            # 获取所有已审核的音频片段
            stmt = select(AudioSegment).where(
                AudioSegment.review_status == "approved",
                AudioSegment.transcription.isnot(None),
            ).order_by(AudioSegment.created_at)

            result = await db.execute(stmt)
            segments = result.scalars().all()

            logger.info(f"找到 {len(segments)} 个已审核的音频片段")

            if not segments:
                logger.warning("没有找到可清洗的音频片段")
                return

            # 分析清洗前的重复率
            pre_stats = await analyze_duplicate_rate(segments)
            logger.info(f"清洗前统计:")
            logger.info(f"  片段总数: {pre_stats['total_segments']}")
            logger.info(f"  句子总数: {pre_stats['total_sentences']}")
            logger.info(f"  重复句子: {pre_stats['duplicate_sentences']}")
            logger.info(f"  重复率: {pre_stats['duplicate_rate_percent']:.2f}%")

            # 清洗每个片段
            processed = 0
            successful = 0
            failed = 0

            for segment in segments:
                processed += 1
                logger.info(f"处理片段 {processed}/{len(segments)}: {segment.id}")

                success = await refine_segment(db, segment)
                if success:
                    successful += 1
                else:
                    failed += 1

                # 每处理10个片段提交一次
                if processed % 10 == 0:
                    await db.commit()
                    logger.info(f"进度: {processed}/{len(segments)}，成功: {successful}，失败: {failed}")

            # 最终提交
            await db.commit()

            # 重新查询清洗后的片段，分析重复率
            logger.info("分析清洗后的重复率...")
            result = await db.execute(stmt)
            cleaned_segments = result.scalars().all()

            post_stats = await analyze_duplicate_rate(cleaned_segments)
            logger.info(f"清洗后统计:")
            logger.info(f"  片段总数: {post_stats['total_segments']}")
            logger.info(f"  句子总数: {post_stats['total_sentences']}")
            logger.info(f"  重复句子: {post_stats['duplicate_sentences']}")
            logger.info(f"  重复率: {post_stats['duplicate_rate_percent']:.2f}%")

            # 计算改进
            improvement = pre_stats['duplicate_rate'] - post_stats['duplicate_rate']
            improvement_percent = improvement * 100

            logger.info(f"清洗结果:")
            logger.info(f"  处理片段: {processed}")
            logger.info(f"  成功清洗: {successful}")
            logger.info(f"  清洗失败: {failed}")
            logger.info(f"  重复率下降: {improvement_percent:.2f}%")
            logger.info(f"  清洗前重复率: {pre_stats['duplicate_rate_percent']:.2f}%")
            logger.info(f"  清洗后重复率: {post_stats['duplicate_rate_percent']:.2f}%")

            # 测试搜索功能
            await test_search_queries(db)

    except Exception as e:
        logger.error(f"数据清洗失败: {str(e)}", exc_info=True)
        raise


async def init_services():
    """初始化所需服务"""
    logger.info("初始化服务...")

    # 初始化数据库
    try:
        await init_db()
        # 确保表存在（开发环境）
        async with db_session.async_session_maker() as session:
            async with session.bind.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logger.info("数据库初始化完成")
    except Exception as e:
        logger.warning(f"数据库初始化失败: {str(e)}")

    # 初始化NLP服务
    try:
        from ai_models.nlp_service import init_nlp_service
        await init_nlp_service()
        logger.info("NLP服务初始化完成")
    except Exception as e:
        logger.warning(f"NLP服务初始化失败: {str(e)}")

    # 初始化向量索引
    try:
        await init_vector_index()
        logger.info("向量索引初始化完成")
    except Exception as e:
        logger.warning(f"向量索引初始化失败: {str(e)}")


async def test_search_queries(db: AsyncSession):
    """
    测试搜索查询，验证清洗效果

    Args:
        db: 数据库会话
    """
    logger.info("=== 测试搜索功能 ===")

    test_queries = ["北京时间", "新闻", "广播", "今天天气"]

    from services.search_service import search_audio_segments_by_text

    for query in test_queries:
        logger.info(f"测试查询: '{query}'")

        try:
            results = await search_audio_segments_by_text(
                query_text=query,
                top_k=3,
                similarity_threshold=settings.SIMILARITY_THRESHOLD,
            )

            if not results:
                logger.warning(f"  查询 '{query}' 未返回结果")
                continue

            logger.info(f"  查询 '{query}' 返回 {len(results)} 个结果:")
            for i, (segment_id, similarity) in enumerate(results):
                logger.info(f"    结果 {i+1}: 片段ID={segment_id}, 相似度={similarity:.4f}")

                # 获取片段详情
                stmt = select(AudioSegment).where(AudioSegment.id == segment_id)
                result_obj = await db.execute(stmt)
                segment = result_obj.scalar_one_or_none()

                if segment:
                    logger.info(f"      文本: {segment.transcription[:100] if segment.transcription else '无'}...")
                    logger.info(f"      时长: {segment.duration:.1f}秒")
                else:
                    logger.warning(f"      片段 {segment_id} 不存在于数据库")

        except Exception as e:
            logger.error(f"测试查询 '{query}' 失败: {str(e)}")


async def main():
    """主函数"""
    try:
        await refine_all_segments()
        logger.info("=== 数据清洗完成 ===")
    except Exception as e:
        logger.error(f"数据清洗过程发生错误: {str(e)}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)