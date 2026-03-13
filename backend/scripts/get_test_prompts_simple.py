#!/usr/bin/env python3
"""
简单版本：获取测试提问
"""
import asyncio
import sys
import random
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import os
# 设置数据库连接
os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import shared.database.session as db_session
from shared.models.audio import AudioSegment
from shared.models.user import User
from shared.models.chat import ChatMessage
from shared.database.session import init_db
from config import settings

# 覆盖设置
settings.DATABASE_URL = os.environ["DATABASE_URL"]

async def get_segments():
    """获取5个有向量的片段"""
    await init_db()

    async with db_session.async_session_maker() as db:
        stmt = select(AudioSegment).where(
            AudioSegment.vector.is_not(None),
            AudioSegment.review_status == "approved",
            AudioSegment.transcription.is_not(None),
            AudioSegment.transcription != "",
            ~AudioSegment.transcription.like("这是语音识别的示例文本%"),
            ~AudioSegment.transcription.like("音频片段 %")
        ).order_by(func.rand()).limit(5)

        result = await db.execute(stmt)
        segments = result.scalars().all()
        return segments

def create_prompt(transcription):
    """根据转录文本创建测试提问"""
    # 简单方法：使用转录文本的前几个词
    words = transcription.split()
    if len(words) >= 3:
        # 取前3个词作为提问基础
        base = "".join(words[:3])
        return f"关于{base}的内容"
    else:
        return f"关于{transcription[:20]}的内容"

async def main():
    print("获取测试提问...")

    segments = await get_segments()

    if not segments:
        print("没有找到符合条件的音频片段")
        return

    print("\n" + "="*60)
    print("测试提问列表 (复制到小程序中测试):")
    print("="*60)

    for i, segment in enumerate(segments, 1):
        transcription = segment.transcription
        prompt = create_prompt(transcription)

        print(f"\n{i}. 测试提问: {prompt}")
        print(f"   广播原声: {transcription}")
        print(f"   片段ID: {segment.id}")

    print("\n" + "="*60)
    print("说明: 将这些提问复制到微信小程序中发送测试匹配效果")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())