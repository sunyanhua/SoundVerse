"""
诊断并修复 pending 状态的音频源

用法:
    docker cp test/scripts/fix_pending_sources.py soundverse-api:/app/scripts/
    docker exec soundverse-api python /app/scripts/fix_pending_sources.py
"""
import asyncio
import sys
sys.path.insert(0, '/app')

from sqlalchemy import select
from shared.models.audio import AudioSource
from services.audio_service import CELERY_AVAILABLE, process_audio_source_task


async def diagnose_pending_sources():
    """诊断 pending 状态的音频源"""
    from shared.database.session import init_db
    await init_db()

    # 重新导入以获取已初始化的 session_maker
    from shared.database.session import async_session_maker

    async with async_session_maker() as db:
        # 查找所有 pending 状态的音频源
        stmt = select(AudioSource).where(
            AudioSource.processing_status == 'pending'
        ).order_by(AudioSource.updated_at.desc())

        result = await db.execute(stmt)
        sources = result.scalars().all()

        if not sources:
            print("✅ 没有发现 pending 状态的音频源")
            return

        print(f"⚠️  发现 {len(sources)} 个 pending 状态的音频源:\n")

        for source in sources:
            print(f"  ID: {source.id}")
            print(f"  标题: {source.title}")
            print(f"  状态: {source.processing_status}")
            print(f"  进度: {source.processing_progress}")
            print(f"  错误信息: {source.error_message}")
            print(f"  更新时间: {source.updated_at}")
            print(f"  文件路径: {source.oss_url}")
            print("-" * 50)

        print(f"\n📊 Celery 可用状态: {CELERY_AVAILABLE}")

        if CELERY_AVAILABLE and process_audio_source_task:
            print("✅ Celery 可用，可以重新提交任务")

            # 询问是否重新提交
            for source in sources:
                print(f"\n🔄 正在重新提交任务: {source.id}")
                try:
                    # 重置状态并提交任务
                    source.processing_status = "processing"
                    source.processing_progress = 0.0
                    await db.commit()

                    # 提交 Celery 任务
                    process_audio_source_task.delay(str(source.id), str(source.user_id or 'admin'))
                    print(f"  ✅ 任务已提交到 Celery")
                except Exception as e:
                    print(f"  ❌ 提交失败: {e}")
                    await db.rollback()
        else:
            print("❌ Celery 不可用，无法提交任务")
            print(f"   CELERY_AVAILABLE={CELERY_AVAILABLE}")
            print(f"   process_audio_source_task={process_audio_source_task}")


if __name__ == "__main__":
    asyncio.run(diagnose_pending_sources())
