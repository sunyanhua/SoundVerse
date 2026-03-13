#!/usr/bin/env python3
"""
清空audio_segments表
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 设置数据库URL
if os.environ.get("DATABASE_URL") is None:
    # 自动检测运行环境：容器内使用mysql，容器外使用localhost
    import os
    if os.path.exists("/.dockerenv"):
        # 在Docker容器内，使用服务名mysql
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"
        print("检测到Docker容器环境，使用mysql:3306")
    else:
        # 在主机上，使用localhost
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"
        print("检测到主机环境，使用localhost:3306")

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import shared.database.session as db_session
from shared.database.session import init_db

async def truncate_audio_segments():
    """清空audio_segments表"""
    print("=== 清空audio_segments表 ===")

    async with db_session.async_session_maker() as db:
        try:
            # 禁用外键检查
            await db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            # 清空audio_segments表
            result = await db.execute(text("TRUNCATE TABLE audio_segments"))
            print(f"[OK] audio_segments表已清空")

            # 启用外键检查
            await db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

            # 提交事务
            await db.commit()
            return True

        except Exception as e:
            print(f"[ERROR] 清空失败: {e}")
            await db.rollback()
            return False

async def count_segments():
    """统计片段数量"""
    async with db_session.async_session_maker() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM audio_segments"))
        count = result.scalar()
        print(f"当前audio_segments表中的记录数: {count}")
        return count

async def main():
    """主函数"""
    print("开始清空音频片段数据...")

    # 初始化数据库
    await init_db()

    # 先统计当前数量
    before = await count_segments()

    if before == 0:
        print("数据库已经是空的")
        return 0

    # 清空表
    success = await truncate_audio_segments()

    if success:
        # 再次统计确认
        after = await count_segments()
        print(f"[OK] 清空完成: {before} -> {after} 条记录")
        return 0
    else:
        print("[ERROR] 清空失败")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)