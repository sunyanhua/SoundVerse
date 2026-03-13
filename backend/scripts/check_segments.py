#!/usr/bin/env python3
"""
检查音频片段数据库统计
"""
import asyncio
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 使用Docker容器内的默认MySQL连接
import os
if os.environ.get("DATABASE_URL") is None:
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import shared.database.session as db_session
from shared.models.audio import AudioSegment
from sqlalchemy.orm import selectinload
from shared.database.session import init_db

async def count_segments() -> int:
    """统计音频片段数量"""
    async with db_session.async_session_maker() as db:
        stmt = select(func.count()).select_from(AudioSegment)
        result = await db.execute(stmt)
        count = result.scalar()
        return count

async def count_real_transcriptions() -> int:
    """统计真实转录文本的数量（排除模拟文本）"""
    async with db_session.async_session_maker() as db:
        # 检查transcription字段是否包含真实内容（排除模拟文本）
        stmt = select(func.count()).select_from(AudioSegment).where(
            AudioSegment.transcription.is_not(None),
            AudioSegment.transcription != "",
            ~AudioSegment.transcription.like("这是语音识别的示例文本%"),
            ~AudioSegment.transcription.like("音频片段 %")
        )
        result = await db.execute(stmt)
        count = result.scalar()
        return count

async def get_random_segment():
    """随机获取一个音频片段"""
    async with db_session.async_session_maker() as db:
        # 获取一个真实转录的片段
        stmt = select(AudioSegment).where(
            AudioSegment.transcription.is_not(None),
            AudioSegment.transcription != "",
            ~AudioSegment.transcription.like("这是语音识别的示例文本%"),
            ~AudioSegment.transcription.like("音频片段 %")
        ).order_by(func.rand()).limit(1)
        result = await db.execute(stmt)
        segment = result.scalar_one_or_none()
        return segment

async def main():
    print("=== 音频片段数据库统计 ===")

    # 初始化数据库
    await init_db()

    total_count = await count_segments()
    real_count = await count_real_transcriptions()

    print(f"音频片段总数: {total_count}")
    print(f"真实转录文本数量: {real_count}")

    if real_count > 0:
        segment = await get_random_segment()
        if segment:
            print(f"\n=== 随机选择一个真实转录片段 ===")
            print(f"片段ID: {segment.id}")
            print(f"起始时间: {segment.start_time:.2f}s")
            print(f"结束时间: {segment.end_time:.2f}s")
            print(f"时长: {segment.duration:.2f}s")
            print(f"\n转录文本: {segment.transcription}")
            print(f"\nOSS URL: {segment.oss_url}")
            print(f"\n提示: 您可以在浏览器中打开此URL收听音频片段")

            # 显示片段信息
            print(f"\n数据库信息:")
            print(f"  创建时间: {segment.created_at}")
            print(f"  来源ID: {segment.source_id}")
            print(f"  语言: {segment.language}")
    else:
        print("没有找到真实转录的音频片段")

if __name__ == "__main__":
    asyncio.run(main())