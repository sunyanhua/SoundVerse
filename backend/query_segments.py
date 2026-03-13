#!/usr/bin/env python3
"""
查询 audio_segments 表的前10条记录
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import shared.database.session as db_session
from shared.models.audio import AudioSegment, AudioSource
from shared.models.user import User
from shared.models.chat import ChatMessage

async def query_segments():
    """查询音频片段"""
    # 初始化数据库
    await db_session.init_db()

    async with db_session.async_session_maker() as db:
        # 查询前10条记录，按创建时间排序
        stmt = select(AudioSegment).order_by(AudioSegment.created_at).limit(10)
        result = await db.execute(stmt)
        segments = result.scalars().all()

        print(f"Found {len(segments)} audio segments")
        print("=" * 80)

        for i, segment in enumerate(segments):
            print(f"Segment {i+1}:")
            print(f"  ID: {segment.id}")
            print(f"  Start time: {segment.start_time:.2f}s")
            print(f"  End time: {segment.end_time:.2f}s")
            print(f"  Transcription (raw_text): {repr(segment.transcription)}")
            if segment.transcription:
                try:
                    print(f"  UTF-8 decoded: {segment.transcription.encode('utf-8', errors='replace').decode('utf-8')}")
                except:
                    pass
            print(f"  OSS URL (audio_url): {segment.oss_url}")
            print(f"  Created at: {segment.created_at}")
            print("-" * 80)

async def main():
    try:
        await query_segments()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)