#!/usr/bin/env python3
"""
清理所有数据脚本：清空数据库和向量索引
"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 使用Docker容器内的默认MySQL连接
import os
if os.environ.get("DATABASE_URL") is None:
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text
from shared.database.session import async_session_maker
from config import settings
from services.search_service import search_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def clear_database():
    """清空数据库"""
    logger.info("开始清空数据库...")

    engine = create_async_engine(settings.DATABASE_URL)

    # 按依赖顺序删除表数据
    tables = [
        "chat_messages",
        "chat_sessions",
        "favorite_segments",
        "audio_segments",
        "audio_sources",
        "users",  # 注意：生产环境可能不想删除用户
    ]

    async with engine.begin() as conn:
        # 禁用外键检查
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in tables:
            try:
                result = await conn.execute(text(f"DELETE FROM {table}"))
                logger.info(f"清空表 {table}: 删除了 {result.rowcount} 行")
            except Exception as e:
                logger.warning(f"清空表 {table} 失败: {str(e)}")

        # 重新启用外键检查
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    logger.info("数据库清空完成")


async def clear_vector_index():
    """清空向量索引"""
    logger.info("开始清空向量索引...")

    try:
        # 初始化搜索服务
        await search_service.initialize()

        # 获取索引统计信息
        stats = await search_service.get_index_stats()
        logger.info(f"当前索引统计: {stats}")

        if stats["engine"] == "dashvector":
            # DashVector: 删除并重新创建Collection
            logger.info("清空DashVector Collection...")
            try:
                # 尝试删除Collection
                client = search_service.dashvector_client
                if client:
                    client.delete(settings.DASHVECTOR_COLLECTION)
                    logger.info(f"删除DashVector Collection: {settings.DASHVECTOR_COLLECTION}")

                    # 重新创建Collection
                    collection = client.create(
                        name=settings.DASHVECTOR_COLLECTION,
                        dimension=settings.DASHVECTOR_COLLECTION_DIMENSION,
                        metric="cosine"
                    )
                    search_service.dashvector_collection = collection
                    logger.info(f"重新创建DashVector Collection: {settings.DASHVECTOR_COLLECTION}")
            except Exception as e:
                logger.error(f"清空DashVector失败: {str(e)}")
        else:
            # FAISS: 删除索引文件并创建空索引
            logger.info("清空FAISS索引...")
            index_path = Path(settings.FAISS_INDEX_PATH)
            metadata_path = index_path.with_suffix('.pkl')

            for file_path in [index_path, metadata_path]:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"删除文件: {file_path}")

            # 创建空索引
            await search_service.create_empty_index()
            logger.info("创建新的空FAISS索引")

        # 获取清理后的统计信息
        stats_after = await search_service.get_index_stats()
        logger.info(f"清理后索引统计: {stats_after}")

    except Exception as e:
        logger.error(f"清空向量索引失败: {str(e)}")
        raise


async def verify_cleanup():
    """验证清理结果"""
    logger.info("验证清理结果...")

    # 验证数据库
    async with async_session_maker() as db:
        from sqlalchemy import select, func
        from shared.models.audio import AudioSegment, AudioSource
        from shared.models.chat import ChatMessage, ChatSession

        # 检查音频片段数量
        result = await db.execute(select(func.count()).select_from(AudioSegment))
        segment_count = result.scalar()
        logger.info(f"音频片段数量: {segment_count}")

        # 检查音频源数量
        result = await db.execute(select(func.count()).select_from(AudioSource))
        source_count = result.scalar()
        logger.info(f"音频源数量: {source_count}")

        # 检查聊天消息数量
        result = await db.execute(select(func.count()).select_from(ChatMessage))
        message_count = result.scalar()
        logger.info(f"聊天消息数量: {message_count}")

        # 检查聊天会话数量
        result = await db.execute(select(func.count()).select_from(ChatSession))
        session_count = result.scalar()
        logger.info(f"聊天会话数量: {session_count}")

        if segment_count == 0 and source_count == 0 and message_count == 0 and session_count == 0:
            logger.info("✅ 数据库清理验证通过")
        else:
            logger.warning("⚠️ 数据库清理不彻底")

    # 验证向量索引
    try:
        stats = await search_service.get_index_stats()
        total_segments = stats.get("total_segments", 0)
        logger.info(f"向量索引片段数量: {total_segments}")

        if total_segments == 0:
            logger.info("✅ 向量索引清理验证通过")
        else:
            logger.warning("⚠️ 向量索引清理不彻底")
    except Exception as e:
        logger.error(f"验证向量索引失败: {str(e)}")


async def main():
    """主函数"""
    logger.info("=== 开始清理所有数据 ===")

    try:
        # 1. 清空数据库
        await clear_database()

        # 2. 清空向量索引
        await clear_vector_index()

        # 3. 验证清理结果
        await verify_cleanup()

        logger.info("=== 数据清理完成 ===")

    except Exception as e:
        logger.error(f"清理过程中发生错误: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)