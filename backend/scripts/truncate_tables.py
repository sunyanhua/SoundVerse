#!/usr/bin/env python3
"""
清空音频相关表，为重新入库做准备
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 加载环境变量
from dotenv import load_dotenv
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import shared.database.session as db_session
from shared.database.session import init_db

async def main():
    """清空音频相关表"""
    print("=== 清空音频相关表 ===")
    print("警告：这将删除所有音频源和音频片段数据！")

    # 自动确认，因为这是用户要求的"拨乱反正"操作
    confirm = "YES"
    print(f"自动确认: {confirm}")

    try:
        # 初始化数据库
        print("初始化数据库连接...")
        await init_db()

        async with db_session.async_session_maker() as session:
            async with session.begin():
                print("清空 audio_segments 表...")
                # 由于外键约束，使用DELETE而不是TRUNCATE
                await session.execute(text("DELETE FROM audio_segments"))

                print("清空 audio_sources 表...")
                await session.execute(text("DELETE FROM audio_sources"))

                print("提交事务...")
                await session.commit()

                print("[OK] 表清空完成")

        # 验证表已清空（使用新的事务）
        async with db_session.async_session_maker() as session2:
            result = await session2.execute(text("SELECT COUNT(*) FROM audio_segments"))
            segment_count = result.scalar()
            result = await session2.execute(text("SELECT COUNT(*) FROM audio_sources"))
            source_count = result.scalar()

            print(f"验证: audio_segments 表行数: {segment_count}")
            print(f"验证: audio_sources 表行数: {source_count}")

            if segment_count == 0 and source_count == 0:
                print("[OK] 验证通过：表已清空")
                return 0
            else:
                print("[ERROR] 验证失败：表未完全清空")
                return 1

    except Exception as e:
        print(f"[ERROR] 清空表失败: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)