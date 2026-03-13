#!/usr/bin/env python3
"""
报告音频片段查询结果
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
    """获取音频片段并解码文本"""
    await db_session.init_db()

    async with db_session.async_session_maker() as db:
        # 查询前10条记录，按创建时间排序
        stmt = select(AudioSegment).order_by(AudioSegment.created_at).limit(10)
        result = await db.execute(stmt)
        segments = result.scalars().all()

        return segments

def decode_hex_text(hex_str):
    """解码十六进制文本"""
    if not hex_str:
        return ""
    try:
        bytes_obj = bytes.fromhex(hex_str)
        return bytes_obj.decode('utf-8')
    except:
        return hex_str

async def main():
    print("=" * 80)
    print("音频片段数据库查询结果")
    print("=" * 80)

    segments = await get_segments()
    print(f"共找到 {len(segments)} 个音频片段")
    print()

    # 获取第一个片段的源信息
    if segments:
        source_id = segments[0].source_id
        async with db_session.async_session_maker() as db:
            stmt = select(AudioSource).where(AudioSource.id == source_id)
            result = await db.execute(stmt)
            source = result.scalar_one_or_none()
            if source:
                print(f"音频源: {source.title}")
                print(f"原始文件: {source.original_filename}")
                print(f"节目类型: {source.program_type}")
                print()

    for i, segment in enumerate(segments):
        print(f"片段 {i+1}:")
        print(f"  ID: {segment.id}")
        print(f"  时间: {segment.start_time:.2f}s - {segment.end_time:.2f}s (时长: {segment.duration:.2f}s)")
        print(f"  转录文本: {segment.transcription}")
        print(f"  OSS URL: {segment.oss_url}")

        # 检查OSS URL是否可以访问
        import urllib.request
        try:
            req = urllib.request.Request(segment.oss_url, method='HEAD')
            response = urllib.request.urlopen(req, timeout=5)
            print(f"  OSS状态: 可访问 (HTTP {response.status})")
        except Exception as e:
            print(f"  OSS状态: 不可访问 ({str(e)[:50]})")

        print()

if __name__ == "__main__":
    asyncio.run(main())