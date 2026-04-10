"""
检查最近的音频源状态

用法:
    MSYS_NO_PATHCONV=1 docker exec soundverse-api python /app/scripts/check_recent_sources.py
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy import select
from shared.database.session import init_db
from shared.models.audio import AudioSource


async def check_recent_sources():
    """检查最近的音频源"""
    await init_db()
    from shared.database.session import async_session_maker

    async with async_session_maker() as db:
        # 查找最近更新的音频源
        stmt = select(AudioSource).order_by(AudioSource.updated_at.desc()).limit(10)
        result = await db.execute(stmt)
        sources = result.scalars().all()

        print("📊 最近更新的 10 个音频源:\n")

        for source in sources:
            status_icon = {
                'completed': '✅',
                'processing': '🔄',
                'pending': '⏳',
                'failed': '❌'
            }.get(source.processing_status, '❓')

            print(f"{status_icon} {source.title}")
            print(f"   ID: {source.id}")
            print(f"   状态: {source.processing_status}")
            print(f"   进度: {source.processing_progress}")
            print(f"   语弹数: {len(source.segments) if hasattr(source, 'segments') else 'N/A'}")
            if source.error_message:
                print(f"   错误: {source.error_message[:100]}")
            print(f"   更新时间: {source.updated_at}")
            print("-" * 50)


if __name__ == "__main__":
    asyncio.run(check_recent_sources())
