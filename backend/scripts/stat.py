#!/usr/bin/env python3
"""
快速统计脚本
"""
import asyncio
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from shared.database.session import async_session_maker
from shared.models.audio import AudioSource, AudioSegment
from services.search_service import vector_client, vector_collection

async def get_db_stats():
    async with async_session_maker() as session:
        # 音频源数量
        result = await session.execute(select(func.count()).select_from(AudioSource))
        total_sources = result.scalar()
        # 音频片段数量
        result = await session.execute(select(func.count()).select_from(AudioSegment))
        total_segments = result.scalar()
        # 已审核的片段数量
        result = await session.execute(select(func.count()).select_from(AudioSegment).where(AudioSegment.review_status == 'approved'))
        approved_segments = result.scalar()
        # 按处理状态统计源
        result = await session.execute(select(AudioSource.processing_status, func.count()).group_by(AudioSource.processing_status))
        status_counts = dict(result.all())
        return {
            'total_sources': total_sources or 0,
            'total_segments': total_segments or 0,
            'approved_segments': approved_segments or 0,
            'source_status': status_counts
        }

async def get_vector_stats():
    """获取DashVector集合统计"""
    try:
        if vector_client and vector_collection:
            # 获取集合信息
            info = vector_collection.describe()
            # 统计向量数量（可能需要使用scan，这里简化）
            # 注意：scan可能消耗资源，暂时跳过
            return {
                'collection_name': info.name,
                'dimension': info.dimension,
                'metric': info.metric,
                'description': info.description,
                'vector_count': '需要scan查询'
            }
        else:
            return {'error': 'DashVector未初始化'}
    except Exception as e:
        return {'error': str(e)}

async def main():
    print("=== 当前统计信息 ===")
    db_stats = await get_db_stats()
    print(f"音频源总数: {db_stats['total_sources']}")
    print(f"音频片段总数: {db_stats['total_segments']}")
    print(f"已审核片段数: {db_stats['approved_segments']}")
    print(f"音频源状态: {db_stats['source_status']}")

    vector_stats = await get_vector_stats()
    print(f"\nDashVector集合: {vector_stats.get('collection_name', 'N/A')}")
    print(f"向量维度: {vector_stats.get('dimension', 'N/A')}")
    print(f"度量方式: {vector_stats.get('metric', 'N/A')}")

    # 尝试获取向量数量（使用scan估计）
    try:
        from services.search_service import vector_collection
        if vector_collection:
            # scan限制返回10条，仅用于演示
            res = vector_collection.scan(limit=10)
            if hasattr(res, 'total'):
                print(f"向量总数（估计）: {res.total}")
            else:
                print("向量总数: 无法获取（需要完整scan）")
    except Exception as e:
        print(f"向量统计错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())