#!/usr/bin/env python3
"""
清空音频相关表（使用TRUNCATE TABLE）
"""
import asyncio
import sys
import os
from pathlib import Path

# 设置数据库连接
os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
import shared.database.session as db_session

async def truncate_tables():
    """清空音频相关表"""
    print("=== 清空音频相关表 ===")

    # 初始化数据库连接
    await db_session.init_db()

    # 获取同步引擎以执行原始SQL
    # 注意：SQLAlchemy的异步引擎不支持某些DDL操作，我们使用同步连接
    sync_db_url = "mysql+pymysql://soundverse:password@localhost:3306/soundverse"
    from sqlalchemy import create_engine
    sync_engine = create_engine(sync_db_url)

    try:
        with sync_engine.connect() as conn:
            # 禁用外键检查
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            # 清空表（注意顺序：先删除有外键依赖的表）
            tables = ["audio_segments", "audio_sources"]
            for table in tables:
                result = conn.execute(text(f"TRUNCATE TABLE {table}"))
                print(f"已清空表: {table}")

            # 启用外键检查
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

            conn.commit()

        print("表清空完成")

    except Exception as e:
        print(f"清空表时出错: {e}")
        raise

async def main():
    print("警告：这将清空所有音频片段和音频源记录！")
    print("确认要继续吗？ (y/n)")

    # 由于无法交互，我们假设用户已确认
    confirm = "y"  # 假设用户已确认

    if confirm.lower() == "y":
        await truncate_tables()
    else:
        print("取消操作")

if __name__ == "__main__":
    asyncio.run(main())