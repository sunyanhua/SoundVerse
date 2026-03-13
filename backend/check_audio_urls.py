#!/usr/bin/env python3
"""
检查音频片段URL
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

import os
os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from shared.models.audio import AudioSegment, AudioSource, FavoriteSegment
from shared.models.user import User, UserToken, UserUsage
from shared.models.chat import ChatSession, ChatMessage

async def check_audio_urls():
    """检查音频片段URL"""
    DATABASE_URL = os.environ["DATABASE_URL"]
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 查询几个音频片段
        stmt = select(AudioSegment).limit(5)
        result = await db.execute(stmt)
        segments = result.scalars().all()

        print("检查音频片段URL:")
        print("=" * 80)

        for i, segment in enumerate(segments, 1):
            print(f"\n{i}. 片段ID: {segment.id[:8]}...")
            print(f"   转录文本: {segment.transcription[:60] if segment.transcription else '无'}")
            print(f"   OSS Key: {segment.oss_key}")
            print(f"   OSS URL: {segment.oss_url}")

            if segment.oss_url:
                if "soundhelix" in segment.oss_url.lower():
                    print("   ⚠️  URL包含'soundhelix' - 这是测试音乐")
                elif "ai-sun" in segment.oss_url.lower() or "vbegin" in segment.oss_url.lower():
                    print("   ⚠️  URL包含测试域名 - 可能被替换为测试音乐")
                else:
                    print("   ✅ URL看起来正常")
            else:
                print("   ❌ OSS URL为空")

        # 检查马里奥赛车相关的片段
        print(f"\n" + "=" * 80)
        print("查找包含'马里奥'或'赛车'的片段:")

        stmt2 = select(AudioSegment).where(
            AudioSegment.transcription.like('%马里奥%') |
            AudioSegment.transcription.like('%赛车%')
        ).limit(3)

        result2 = await db.execute(stmt2)
        mario_segments = result2.scalars().all()

        if mario_segments:
            for i, segment in enumerate(mario_segments, 1):
                print(f"\n{i}. 片段ID: {segment.id[:8]}...")
                print(f"   转录文本: {segment.transcription[:80] if segment.transcription else '无'}")
                print(f"   OSS URL: {segment.oss_url}")
        else:
            print("   未找到包含'马里奥'或'赛车'的片段")

async def main():
    await check_audio_urls()

if __name__ == "__main__":
    asyncio.run(main())