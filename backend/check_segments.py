#!/usr/bin/env python3
"""
检查音频片段并正确输出UTF-8编码
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# 设置数据库连接
os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import shared.database.session as db_session
from shared.models.audio import AudioSegment, AudioSource
from shared.models.user import User
from shared.models.chat import ChatMessage

async def get_segments():
    """获取音频片段"""
    await db_session.init_db()

    async with db_session.async_session_maker() as db:
        # 查询前10条记录，按创建时间排序
        stmt = select(AudioSegment).order_by(AudioSegment.created_at).limit(10)
        result = await db.execute(stmt)
        segments = result.scalars().all()

        return segments

async def main():
    # 设置标准输出编码为UTF-8
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 80)
    print("音频片段数据库查询结果 (UTF-8编码)")
    print("=" * 80)

    segments = await get_segments()
    print(f"共找到 {len(segments)} 个音频片段")
    print()

    for i, segment in enumerate(segments):
        print(f"片段 {i+1}:")
        print(f"  ID: {segment.id}")
        print(f"  时间: {segment.start_time:.2f}s - {segment.end_time:.2f}s (时长: {segment.duration:.2f}s)")
        print(f"  转录文本: {segment.transcription}")
        print(f"  OSS URL: {segment.oss_url}")
        print()

if __name__ == "__main__":
    asyncio.run(main())