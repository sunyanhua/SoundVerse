#!/usr/bin/env python3
"""
彻底清空数据库和DashVector向量索引
用于完全重新开始，拒绝旧账
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

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import shared.database.session as db_session
from shared.database.session import init_db, Base
from config import settings
from services.search_service import search_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def clear_database(db: AsyncSession):
    """清空数据库中的所有音频数据"""
    logger.info("=== 开始清空数据库 ===")

    try:
        # 按照外键约束顺序删除
        # 1. 先删除聊天消息（引用audio_segments）
        await db.execute(text("DELETE FROM chat_messages"))
        logger.info("清空 chat_messages 表")

        # 2. 清空收藏表（引用audio_segments）
        await db.execute(text("DELETE FROM favorite_segments"))
        logger.info("清空 favorite_segments 表")

        # 3. 清空音频片段表
        await db.execute(text("DELETE FROM audio_segments"))
        logger.info("清空 audio_segments 表")

        # 4. 清空音频源表
        await db.execute(text("DELETE FROM audio_sources"))
        logger.info("清空 audio_sources 表")

        # 5. 清空聊天会话表（可选）
        await db.execute(text("DELETE FROM chat_sessions"))
        logger.info("清空 chat_sessions 表")

        # 重置自增ID（可选）
        # await db.execute(text("ALTER TABLE audio_segments AUTO_INCREMENT = 1"))
        # await db.execute(text("ALTER TABLE audio_sources AUTO_INCREMENT = 1"))
        # await db.execute(text("ALTER TABLE favorite_segments AUTO_INCREMENT = 1"))

        await db.commit()
        logger.info("数据库清空完成")

    except Exception as e:
        logger.error(f"清空数据库失败: {str(e)}")
        await db.rollback()
        raise


async def clear_dashvector_collection():
    """清空DashVector集合中的所有向量数据"""
    logger.info("=== 开始清空DashVector向量数据 ===")

    try:
        # 初始化搜索服务
        await search_service.initialize()

        if search_service.use_dashvector and search_service.dashvector_client:
            # 删除整个collection
            try:
                search_service.dashvector_client.delete(search_service.dashvector_collection_name)
                logger.info(f"删除DashVector Collection: {search_service.dashvector_collection_name}")

                # 重新创建collection
                collection = search_service.dashvector_client.create(
                    name=search_service.dashvector_collection_name,
                    dimension=settings.DASHVECTOR_COLLECTION_DIMENSION,
                    metric='cosine'  # 使用余弦相似度
                )
                search_service.dashvector_collection = collection
                logger.info(f"重新创建DashVector Collection: {search_service.dashvector_collection_name}")

            except Exception as e:
                logger.error(f"删除/重建DashVector Collection失败: {str(e)}")
                # 如果删除失败，尝试清空所有文档
                try:
                    # 获取所有文档并删除
                    docs = search_service.dashvector_collection.scan()
                    doc_ids = [doc.id for doc in docs]
                    if doc_ids:
                        search_service.dashvector_collection.delete(doc_ids)
                        logger.info(f"删除DashVector中的 {len(doc_ids)} 个文档")
                except Exception as e2:
                    logger.error(f"清空DashVector文档失败: {str(e2)}")
        else:
            logger.warning("DashVector未配置，跳过DashVector清空")

    except Exception as e:
        logger.error(f"清空DashVector失败: {str(e)}")
        raise


async def clear_faiss_index():
    """清空本地FAISS索引"""
    logger.info("=== 开始清空FAISS索引 ===")

    try:
        # 删除索引文件
        import os
        faiss_index_path = Path(settings.FAISS_INDEX_PATH)
        metadata_path = faiss_index_path.with_suffix('.pkl')

        if faiss_index_path.exists():
            os.remove(faiss_index_path)
            logger.info(f"删除FAISS索引文件: {faiss_index_path}")

        if metadata_path.exists():
            os.remove(metadata_path)
            logger.info(f"删除FAISS元数据文件: {metadata_path}")

        # 重置搜索服务状态
        search_service.index = None
        search_service.segment_ids = []
        search_service.initialized = False

        # 创建空索引
        await search_service.create_empty_index()
        logger.info("创建新的空FAISS索引")

    except Exception as e:
        logger.error(f"清空FAISS索引失败: {str(e)}")
        raise


async def verify_clear_status(db: AsyncSession):
    """验证清空状态"""
    logger.info("=== 验证清空状态 ===")

    try:
        # 检查数据库记录数
        from sqlalchemy import text
        from shared.models.audio import AudioSegment, AudioSource

        # 检查音频片段数量
        result = await db.execute(text("SELECT COUNT(*) as count FROM audio_segments"))
        segment_count = result.scalar()
        logger.info(f"audio_segments 表记录数: {segment_count}")

        # 检查音频源数量
        result = await db.execute(text("SELECT COUNT(*) as count FROM audio_sources"))
        source_count = result.scalar()
        logger.info(f"audio_sources 表记录数: {source_count}")

        # 检查向量索引状态
        stats = await search_service.get_index_stats()
        logger.info(f"向量索引状态: {stats}")

        if segment_count == 0 and source_count == 0:
            logger.info("✅ 数据库清空验证通过")
        else:
            logger.error("❌ 数据库清空验证失败")

    except Exception as e:
        logger.error(f"验证清空状态失败: {str(e)}")


async def main():
    """主函数"""
    try:
        logger.info("=== 开始彻底清空数据库和向量索引 ===")

        # 初始化数据库连接
        await init_db()

        # 创建数据库会话
        async with db_session.async_session_maker() as db:
            # 1. 清空数据库
            await clear_database(db)

            # 2. 清空向量索引（DashVector或FAISS）
            await clear_dashvector_collection()
            await clear_faiss_index()

            # 3. 验证清空状态
            await verify_clear_status(db)

        logger.info("=== 清空完成 ===")

    except Exception as e:
        logger.error(f"清空过程发生错误: {str(e)}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)