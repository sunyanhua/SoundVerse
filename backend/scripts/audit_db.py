#!/usr/bin/env python3
"""
数据库审计脚本
统计audio_sources表中的文件名，以及audio_segments表中各有多少条对应记录
确认是否包含《一路畅通》、《行走天下》、《北京新闻》等内容
"""
import asyncio
import sys
import os
from pathlib import Path
from collections import defaultdict

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 使用Docker容器内的默认MySQL连接
if os.environ.get("DATABASE_URL") is None:
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import shared.database.session as db_session
from shared.models.audio import AudioSource, AudioSegment
from shared.models.user import User
from shared.models.chat import ChatMessage, ChatSession
from services.search_service import search_service


async def get_audio_sources_stats():
    """获取音频源统计信息"""
    async with db_session.async_session_maker() as session:
        # 统计音频源总数
        result = await session.execute(select(func.count()).select_from(AudioSource))
        total_sources = result.scalar() or 0

        # 获取所有音频源及其文件名
        result = await session.execute(
            select(AudioSource.id, AudioSource.title, AudioSource.original_filename)
        )
        sources = result.all()

        # 获取每个音频源的片段数量
        source_stats = []
        for source_id, title, filename in sources:
            # 统计该源的片段数量
            result = await session.execute(
                select(func.count()).select_from(AudioSegment)
                .where(AudioSegment.source_id == source_id)
            )
            segment_count = result.scalar() or 0

            # 统计该源已审核的片段数量
            result = await session.execute(
                select(func.count()).select_from(AudioSegment)
                .where(
                    AudioSegment.source_id == source_id,
                    AudioSegment.review_status == 'approved'
                )
            )
            approved_count = result.scalar() or 0

            source_stats.append({
                'id': source_id,
                'title': title,
                'filename': filename,
                'segment_count': segment_count,
                'approved_count': approved_count
            })

        return total_sources, source_stats


async def check_content_coverage():
    """检查是否包含特定节目内容"""
    async with db_session.async_session_maker() as session:
        # 定义要检查的关键词
        keywords = [
            ('一路畅通', '《一路畅通》'),
            ('行走天下', '《行走天下》'),
            ('北京新闻', '《北京新闻》'),
            ('新闻广播', '新闻广播'),
            ('中央人民广播电台', '中央人民广播电台'),
            ('中国之声', '中国之声'),
            ('新闻联播', '新闻联播'),
            ('财经新闻', '财经新闻'),
            ('体育新闻', '体育新闻'),
            ('天气预报', '天气预报'),
        ]

        coverage_results = []

        for keyword, display_name in keywords:
            # 在音频源标题中搜索
            result = await session.execute(
                select(func.count()).select_from(AudioSource)
                .where(AudioSource.title.like(f'%{keyword}%'))
            )
            source_count = result.scalar() or 0

            # 在音频片段转录文本中搜索
            result = await session.execute(
                select(func.count()).select_from(AudioSegment)
                .where(AudioSegment.transcription.like(f'%{keyword}%'))
            )
            segment_count = result.scalar() or 0

            coverage_results.append({
                'keyword': display_name,
                'source_count': source_count,
                'segment_count': segment_count,
                'found': source_count > 0 or segment_count > 0
            })

        return coverage_results


async def get_vector_stats():
    """获取DashVector向量统计"""
    try:
        # 确保search_service已初始化
        if not hasattr(search_service, 'dashvector_collection') or search_service.dashvector_collection is None:
            return {'error': 'DashVector未初始化'}

        # 获取集合信息
        info = search_service.dashvector_collection.describe()

        # 尝试获取向量数量（使用scan）
        try:
            res = search_service.dashvector_collection.scan(limit=1)
            if hasattr(res, 'total'):
                vector_count = res.total
            else:
                vector_count = "无法获取（需要完整scan）"
        except Exception as e:
            vector_count = f"scan错误: {e}"

        return {
            'collection_name': info.name,
            'dimension': info.dimension,
            'metric': info.metric,
            'description': info.description,
            'vector_count': vector_count
        }
    except Exception as e:
        return {'error': str(e)}


async def get_detailed_sample():
    """获取详细样本信息"""
    async with db_session.async_session_maker() as session:
        # 获取一个样本音频源
        result = await session.execute(
            select(AudioSource).limit(1)
        )
        sample_source = result.scalar_one_or_none()

        sample_info = {}
        if sample_source:
            # 获取该源的片段
            result = await session.execute(
                select(AudioSegment)
                .where(AudioSegment.source_id == sample_source.id)
                .limit(3)
            )
            sample_segments = result.scalars().all()

            sample_info = {
                'source': {
                    'id': sample_source.id,
                    'title': sample_source.title,
                    'filename': sample_source.original_filename,
                    'program_type': sample_source.program_type,
                    'episode_number': sample_source.episode_number,
                    'broadcast_date': sample_source.broadcast_date,
                    'duration': sample_source.duration,
                    'format': sample_source.format,
                },
                'segments': []
            }

            for segment in sample_segments:
                sample_info['segments'].append({
                    'id': segment.id,
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'duration': segment.duration,
                    'transcription_preview': segment.transcription[:100] + '...' if segment.transcription else None,
                    'review_status': segment.review_status,
                    'vector_dimension': segment.vector_dimension,
                })

        return sample_info


async def main():
    print("=== 数据库审计报告 ===")
    print()

    # 初始化数据库
    await db_session.init_db()

    print("1. 音频源统计")
    print("=" * 50)

    total_sources, source_stats = await get_audio_sources_stats()
    print(f"音频源总数: {total_sources}")
    print()

    print("音频源详细信息:")
    print("-" * 80)
    print(f"{'序号':<5} {'标题':<30} {'文件名':<40} {'片段数':<10} {'已审核数':<10}")
    print("-" * 80)

    for i, stat in enumerate(source_stats, 1):
        # 截断长字符串以便显示
        title = stat['title'][:28] + '..' if len(stat['title']) > 30 else stat['title']
        filename = stat['filename'][:38] + '..' if len(stat['filename']) > 40 else stat['filename']
        print(f"{i:<5} {title:<30} {filename:<40} {stat['segment_count']:<10} {stat['approved_count']:<10}")

    print()

    print("2. 内容覆盖检查")
    print("=" * 50)

    coverage_results = await check_content_coverage()
    print(f"{'节目/内容':<20} {'音频源数':<10} {'片段数':<10} {'是否找到':<10}")
    print("-" * 50)

    found_count = 0
    for result in coverage_results:
        found = '✅' if result['found'] else '❌'
        print(f"{result['keyword']:<20} {result['source_count']:<10} {result['segment_count']:<10} {found:<10}")
        if result['found']:
            found_count += 1

    print(f"\n总计找到 {found_count}/{len(coverage_results)} 个节目内容")
    print()

    print("3. DashVector向量统计")
    print("=" * 50)

    vector_stats = await get_vector_stats()
    if 'error' in vector_stats:
        print(f"错误: {vector_stats['error']}")
    else:
        print(f"集合名称: {vector_stats['collection_name']}")
        print(f"向量维度: {vector_stats['dimension']}")
        print(f"度量方式: {vector_stats['metric']}")
        print(f"描述: {vector_stats['description']}")
        print(f"向量数量: {vector_stats['vector_count']}")

    print()

    print("4. 样本详细信息")
    print("=" * 50)

    sample_info = await get_detailed_sample()
    if sample_info:
        source = sample_info['source']
        print(f"样本音频源:")
        print(f"  标题: {source['title']}")
        print(f"  文件名: {source['filename']}")
        print(f"  节目类型: {source['program_type']}")
        print(f"  期号: {source['episode_number']}")
        print(f"  播出日期: {source['broadcast_date']}")
        print(f"  时长: {source['duration']:.2f}秒")
        print(f"  格式: {source['format']}")
        print()

        print(f"样本片段 (前{len(sample_info['segments'])}个):")
        for i, segment in enumerate(sample_info['segments'], 1):
            print(f"  片段{i}:")
            print(f"    时间: {segment['start_time']:.2f}s - {segment['end_time']:.2f}s ({segment['duration']:.2f}s)")
            print(f"    转录: {segment['transcription_preview']}")
            print(f"    审核状态: {segment['review_status']}")
            print(f"    向量维度: {segment['vector_dimension']}")
    else:
        print("未找到样本音频源")

    print()
    print("=== 审计完成 ===")


if __name__ == "__main__":
    asyncio.run(main())