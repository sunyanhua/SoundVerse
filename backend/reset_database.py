#!/usr/bin/env python3
"""
彻底重置数据库表：清空audio_segments和audio_sources表
"""
import asyncio
import logging
from sqlalchemy import text
from shared.database.session import init_db, async_session_maker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def reset_database():
    """清空相关数据库表"""
    try:
        # 初始化数据库
        await init_db()

        async with async_session_maker() as session:
            # 禁用外键检查（MySQL）
            await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

            # 清空表（注意顺序：先子表后父表）
            tables = ["audio_segments", "audio_sources"]
            for table in tables:
                logger.info(f"清空表: {table}")
                await session.execute(text(f"TRUNCATE TABLE {table}"))
                logger.info(f"表 {table} 已清空")

            # 启用外键检查
            await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

            await session.commit()
            logger.info("数据库表重置完成")
            return True

    except Exception as e:
        logger.error(f"重置数据库失败: {e}")
        return False

async def main():
    logger.info("=== 开始彻底重置数据库表 ===")

    success = await reset_database()

    if success:
        logger.info("=== 数据库表重置成功 ===")
        return 0
    else:
        logger.error("=== 数据库表重置失败 ===")
        return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)