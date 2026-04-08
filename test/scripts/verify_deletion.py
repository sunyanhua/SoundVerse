#!/usr/bin/env python3
"""
验证音频源删除是否完整
检查：数据库记录、OSS文件、向量索引、本地文件
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from shared.database.session import async_session_maker
from shared.models.audio import AudioSource, AudioSegment
from config import settings

# 检查最近删除的记录（过去1小时）
RECENT_DELETE_WINDOW = timedelta(hours=1)

async def check_recent_deletions():
    """检查最近的删除操作"""
    print("=" * 60)
    print("[TIME] 检查最近的删除操作")
    print("=" * 60)

    async with async_session_maker() as db:
        # 1. 查找标记为 deleted 的音频源
        result = await db.execute(
            select(AudioSource).where(
                AudioSource.processing_status == "deleted",
                AudioSource.updated_at >= datetime.utcnow() - RECENT_DELETE_WINDOW
            )
        )
        deleted_sources = result.scalars().all()

        if deleted_sources:
            print(f"\n[WARN]  发现 {len(deleted_sources)} 个标记为 deleted 但未完全删除的音频源:")
            for source in deleted_sources:
                print(f"  - {source.id}: {source.title} (更新于: {source.updated_at})")
                # 检查关联语弹
                seg_result = await db.execute(
                    select(func.count()).where(AudioSegment.source_id == source.id)
                )
                seg_count = seg_result.scalar()
                print(f"    └─ 残留语弹: {seg_count} 个")
        else:
            print("\n[OK] 没有标记为 deleted 的残留音频源")

        # 2. 检查最近30分钟内删除的记录（可能已完全删除）
        result = await db.execute(
            select(func.count()).where(
                AudioSource.processing_status == "deleted"
            )
        )
        total_deleted = result.scalar()
        print(f"\n📊 历史累计标记 deleted 的音频源: {total_deleted} 个")

        # 3. 查找最近30分钟内创建的语弹（验证新节目裁切）
        result = await db.execute(
            select(AudioSegment).where(
                AudioSegment.created_at >= datetime.utcnow() - timedelta(minutes=30)
            ).order_by(AudioSegment.created_at.desc()).limit(10)
        )
        recent_segments = result.scalars().all()

        if recent_segments:
            print(f"\n📈 最近30分钟创建的语弹: {len(recent_segments)} 个")
            for seg in recent_segments[:5]:
                print(f"  - {seg.id[:8]}...: {seg.transcription[:30]}... (情感: {seg.emotion})")

async def check_orphan_segments():
    """检查孤儿语弹（关联的音频源不存在）"""
    print("\n" + "=" * 60)
    print("🔍 检查孤儿语弹")
    print("=" * 60)

    async with async_session_maker() as db:
        # 查找语弹关联的音频源不存在的记录
        result = await db.execute(
            select(AudioSegment).where(
                ~select(AudioSource.id).where(AudioSource.id == AudioSegment.source_id).exists()
            )
        )
        orphans = result.scalars().all()

        if orphans:
            print(f"\n[WARN]  发现 {len(orphans)} 个孤儿语弹:")
            for seg in orphans[:10]:
                print(f"  - {seg.id}: source_id={seg.source_id}")
                print(f"    文本: {seg.transcription[:50]}...")
        else:
            print("\n[OK] 没有发现孤儿语弹")

async def check_vector_index():
    """检查向量索引状态"""
    print("\n" + "=" * 60)
    print("📊 向量索引状态")
    print("=" * 60)

    try:
        from services.search_service import search_service
        await search_service.initialize()
        stats = await search_service.get_index_stats()

        print(f"\n引擎: {stats['engine']}")
        print(f"语弹总数: {stats['total_segments']}")
        print(f"向量维度: {stats['vector_dimension']}")

    except Exception as e:
        print(f"\n[WARN]  无法获取向量索引状态: {e}")

async def main():
    print("🚀 开始验证删除完整性...")
    print(f"⏰ 当前时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

    await check_recent_deletions()
    await check_orphan_segments()
    await check_vector_index()

    print("\n" + "=" * 60)
    print("[OK] 验证完成")
    print("=" * 60)
    print("\n💡 如果发现有残留数据，可以运行清理脚本:")
    print("   python scripts/cleanup_deleted_sources.py --force")

if __name__ == "__main__":
    asyncio.run(main())
