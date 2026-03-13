#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import os
os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from shared.models.audio import AudioSegment
from shared.models.user import User
from shared.models.chat import ChatMessage

async def main():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        stmt = select(AudioSegment).where(
            AudioSegment.vector.is_not(None),
            AudioSegment.review_status == 'approved',
            AudioSegment.transcription.is_not(None),
            AudioSegment.transcription != '',
        ).order_by(func.rand()).limit(5)

        result = await db.execute(stmt)
        segments = result.scalars().all()

        print("=== 5个测试提问及其广播原声内容 ===")
        print()

        for i, seg in enumerate(segments, 1):
            text = seg.transcription
            # 打印原始字符串表示
            print(f"{i}. 【广播原声内容】: {text}")

            # 生成测试提问
            if "新闻" in text:
                prompt = f"有什么新闻相关的广播内容吗？"
            elif "天气" in text or "气温" in text:
                prompt = f"今天的天气怎么样？"
            elif "时间" in text or "点" in text:
                prompt = f"现在是什么时间？"
            elif "体育" in text:
                prompt = f"有什么体育新闻？"
            else:
                # 通用提问
                words = text[:20].split()
                if len(words) > 2:
                    prompt = f"关于{' '.join(words[:2])}的内容"
                else:
                    prompt = f"关于{text[:15]}的内容"

            print(f"   【测试提问】: {prompt}")
            print(f"   【片段ID】: {seg.id}")
            print()

asyncio.run(main())