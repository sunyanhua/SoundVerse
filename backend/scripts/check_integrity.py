#!/usr/bin/env python3
"""
全库缺漏审计脚本

统计 audio_sources 表中每个文件对应的 audio_segments 数量。
对比'总时长'与'切片总时长'。如果发现某个文件对应的切片数明显不足，将其标记为'待补齐'。
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
import logging

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 使用Docker容器内的默认MySQL连接
if os.environ.get("DATABASE_URL") is None:
    if os.path.exists("/.dockerenv"):
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"
    else:
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import shared.database.session as db_session
from shared.models.audio import AudioSource, AudioSegment
from shared.models.user import User
from shared.models.chat import ChatMessage
from shared.database.session import init_db


async def get_source_segment_stats(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    获取每个音频源的片段统计信息

    Returns:
        List of dicts with keys: source_id, title, original_filename, duration,
        segment_count, total_segment_duration, avg_segment_duration, expected_segments
    """
    # 查询所有音频源
    stmt = select(AudioSource)
    result = await db.execute(stmt)
    sources = result.scalars().all()

    stats = []

    for source in sources:
        # 统计该源的片段
        segment_stmt = select(
            func.count().label('count'),
            func.sum(AudioSegment.duration).label('total_duration'),
            func.avg(AudioSegment.duration).label('avg_duration')
        ).where(AudioSegment.source_id == source.id)

        segment_result = await db.execute(segment_stmt)
        segment_data = segment_result.first()

        segment_count = segment_data.count or 0
        total_segment_duration = segment_data.total_duration or 0.0
        avg_segment_duration = segment_data.avg_duration or 0.0

        # 计算预期片段数量（基于平均片段时长 5-10 秒）
        # 使用保守估计：平均 7.5 秒每个片段
        expected_segments = int(source.duration / 7.5) if source.duration > 0 else 0

        # 计算覆盖率（片段总时长 / 源总时长）
        coverage = total_segment_duration / source.duration if source.duration > 0 else 0

        stats.append({
            'source_id': source.id,
            'title': source.title,
            'original_filename': source.original_filename,
            'source_duration': source.duration,
            'segment_count': segment_count,
            'total_segment_duration': total_segment_duration,
            'avg_segment_duration': avg_segment_duration,
            'expected_segments': expected_segments,
            'coverage': coverage,
            'processing_status': source.processing_status,
            'processing_progress': source.processing_progress,
            'error_message': source.error_message
        })

    return stats


def classify_sources(stats: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    分类音频源

    Returns:
        (completed_sources, incomplete_sources, problematic_sources)
    """
    completed = []
    incomplete = []
    problematic = []

    for stat in stats:
        # 标记为"待补齐"的条件：
        # 1. 片段覆盖率 < 70% 且预期片段数 > 10
        # 2. 或者片段数量明显少于预期（< 50%）
        # 3. 或者处理状态为 completed 但片段数很少

        is_incomplete = False
        reasons = []

        # 条件1：覆盖率低
        if stat['coverage'] < 0.7 and stat['expected_segments'] > 10:
            is_incomplete = True
            reasons.append(f"覆盖率低 ({stat['coverage']:.1%})")

        # 条件2：片段数量少于预期的50%
        if stat['expected_segments'] > 0 and stat['segment_count'] < stat['expected_segments'] * 0.5:
            is_incomplete = True
            reasons.append(f"片段数不足 ({stat['segment_count']}/{stat['expected_segments']})")

        # 条件3：状态为completed但片段数很少
        if stat['processing_status'] == 'completed' and stat['segment_count'] < 10 and stat['source_duration'] > 300:  # 5分钟以上但少于10个片段
            is_incomplete = True
            reasons.append(f"状态已完成但片段数少 ({stat['segment_count']})")

        # 条件4：状态为failed
        if stat['processing_status'] == 'failed':
            problematic.append({**stat, 'reasons': [f"处理失败: {stat['error_message']}"]})
            continue

        if is_incomplete:
            incomplete.append({**stat, 'reasons': reasons})
        else:
            completed.append(stat)

    return completed, incomplete, problematic


async def main():
    """主函数"""
    logger.info("=== 全库缺漏审计开始 ===")

    try:
        # 初始化数据库
        await init_db()

        async with db_session.async_session_maker() as db:
            stats = await get_source_segment_stats(db)

            # 分类
            completed, incomplete, problematic = classify_sources(stats)

            # 输出总体统计
            logger.info(f"音频源总数: {len(stats)}")
            logger.info(f"完整处理: {len(completed)}")
            logger.info(f"待补齐: {len(incomplete)}")
            logger.info(f"有问题: {len(problematic)}")

            # 输出待补齐的音频源详情
            if incomplete:
                logger.info("\n=== 待补齐音频源 ===")
                for i, src in enumerate(incomplete, 1):
                    logger.info(f"{i}. {src['title']} ({src['original_filename']})")
                    logger.info(f"   源时长: {src['source_duration']:.1f}s, 片段数: {src['segment_count']}, 预期: {src['expected_segments']}")
                    logger.info(f"   覆盖率: {src['coverage']:.1%}, 状态: {src['processing_status']}")
                    logger.info(f"   原因: {', '.join(src['reasons'])}")
                    logger.info(f"   源ID: {src['source_id']}")
                    logger.info("")

            # 输出有问题的音频源
            if problematic:
                logger.info("\n=== 有问题音频源 ===")
                for i, src in enumerate(problematic, 1):
                    logger.info(f"{i}. {src['title']} ({src['original_filename']})")
                    logger.info(f"   错误: {src['error_message']}")
                    logger.info("")

            # 输出完整处理的音频源
            if completed:
                logger.info("\n=== 完整处理音频源 ===")
                for i, src in enumerate(completed[:20], 1):  # 最多显示20个
                    logger.info(f"{i}. {src['title']}: {src['segment_count']}片段, 覆盖率: {src['coverage']:.1%}")

                if len(completed) > 20:
                    logger.info(f"   ... 还有 {len(completed) - 20} 个完整音频源")

            # 保存详细结果到文件
            import json
            from datetime import datetime
            result_file = backend_dir / "storage" / f"integrity_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            result_file.parent.mkdir(parents=True, exist_ok=True)

            result = {
                'timestamp': datetime.now().isoformat(),
                'total_sources': len(stats),
                'completed_sources': len(completed),
                'incomplete_sources': len(incomplete),
                'problematic_sources': len(problematic),
                'incomplete_details': incomplete,
                'problematic_details': problematic,
                'all_stats': stats
            }

            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"\n详细审计结果已保存到: {result_file}")

            # 返回退出码（如果有待补齐的源，返回1）
            if incomplete or problematic:
                logger.warning("发现待补齐或有问题的音频源，需要处理")
                return 1
            else:
                logger.info("所有音频源完整性良好")
                return 0

    except Exception as e:
        logger.error(f"审计失败: {str(e)}", exc_info=True)
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)