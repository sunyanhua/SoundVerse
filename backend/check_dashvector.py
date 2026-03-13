#!/usr/bin/env python3
"""
检查DashVector集合状态
"""
import asyncio
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from services.search_service import search_service
from shared.database.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_collection():
    """检查集合状态"""
    try:
        # 初始化向量索引
        await search_service.initialize()

        # 获取索引统计
        stats = await search_service.get_index_stats()
        logger.info(f"索引统计: {stats}")

        # 如果使用DashVector，尝试获取更多信息
        if search_service.use_dashvector and search_service.dashvector_collection:
            try:
                collection_stats = search_service.dashvector_collection.stats()
                logger.info(f"DashVector集合统计: {collection_stats}")

                if hasattr(collection_stats, 'total_count'):
                    logger.info(f"总文档数: {collection_stats.total_count}")
                if hasattr(collection_stats, 'dimension'):
                    logger.info(f"向量维度: {collection_stats.dimension}")

                # 尝试获取一个文档样本
                try:
                    # 搜索一个随机查询看看
                    from ai_models.nlp_service import get_text_vector
                    test_vector = await get_text_vector("测试")
                    if test_vector:
                        results = search_service.dashvector_collection.query(
                            vector=test_vector,
                            topk=1
                        )
                        logger.info(f"测试查询结果: {results}")
                except Exception as e:
                    logger.error(f"测试查询失败: {str(e)}")

            except Exception as e:
                logger.error(f"获取集合统计失败: {str(e)}")

        return True

    except Exception as e:
        logger.error(f"检查集合失败: {str(e)}")
        return False

async def main():
    """主函数"""
    logger.info("=== 检查DashVector集合状态 ===")

    success = await check_collection()

    if success:
        logger.info("检查完成")
        return 0
    else:
        logger.error("检查失败")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)