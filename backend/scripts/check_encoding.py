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

async def main():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        stmt = select(AudioSegment).where(
            AudioSegment.vector.is_not(None),
            AudioSegment.review_status == 'approved',
            AudioSegment.transcription.is_not(None),
            AudioSegment.transcription != '',
        ).order_by(func.rand()).limit(3)

        result = await db.execute(stmt)
        segments = result.scalars().all()

        print("=== 检查转录文本编码 ===")
        print(f"Python默认编码: {sys.getdefaultencoding()}")
        print(f"文件系统编码: {sys.getfilesystemencoding()}")
        print()

        for i, seg in enumerate(segments, 1):
            text = seg.transcription
            print(f"片段 {i} (ID: {seg.id}):")
            print(f"  文本长度: {len(text)}")
            print(f"  文本类型: {type(text)}")

            # 打印原始字节
            if isinstance(text, str):
                bytes_repr = text.encode('utf-8', errors='replace')
                print(f"  UTF-8 字节: {bytes_repr[:100]}...")
                print(f"  十六进制: {bytes_repr[:50].hex()}")

                # 尝试不同编码
                try:
                    gbk_bytes = text.encode('gbk', errors='replace')
                    print(f"  GBK 字节: {gbk_bytes[:100]}...")
                except Exception as e:
                    print(f"  GBK 编码错误: {e}")
            else:
                print(f"  非字符串类型: {text}")

            # 打印文本内容（尝试不同方式）
            print(f"  文本内容:")
            print(f"    repr: {repr(text)}")
            print(f"    str: {text}")
            print()

asyncio.run(main())