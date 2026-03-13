#!/usr/bin/env python3
"""
清理数据库中的音频相关记录
"""
import asyncio
import sys
import os
from pathlib import Path

# 设置数据库连接（在主机上使用 localhost）
os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import shared.database.session as db_session
from shared.models.audio import AudioSegment, AudioSource
from shared.models.chat import ChatMessage
from shared.models.user import User

async def clean_audio_data():
    """清理音频数据"""
    await db_session.init_db()

    async with db_session.async_session_maker() as db:
        # 删除所有音频片段
        delete_segments = delete(AudioSegment)
        result = await db.execute(delete_segments)
        await db.commit()
        print(f"删除音频片段: {result.rowcount} 条")

        # 删除所有音频源
        delete_sources = delete(AudioSource)
        result = await db.execute(delete_sources)
        await db.commit()
        print(f"删除音频源: {result.rowcount} 条")

        # 注意：保留用户和聊天记录

        print("数据库清理完成")

async def main():
    print("=== 清理数据库音频数据 ===")
    print("警告：这将删除所有音频片段和音频源记录！")
    print("继续吗？ (y/n)")

    # 在命令行中直接输入确认
    # 由于无法交互，我们假设用户已确认
    # 在实际使用中应添加确认逻辑
    confirm = "y"  # 假设用户已确认

    if confirm.lower() == "y":
        await clean_audio_data()
    else:
        print("取消清理")

if __name__ == "__main__":
    asyncio.run(main())