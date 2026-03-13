#!/usr/bin/env python3
"""
强制重置DashVector向量库：彻底删除并重新创建audio_segments集合
"""
import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def reset_dashvector_collection():
    """重置DashVector集合"""
    try:
        import dashvector

        # 检查DashVector配置
        if not settings.DASHVECTOR_API_KEY or not settings.DASHVECTOR_ENDPOINT:
            logger.error("DashVector配置不完整，请检查DASHVECTOR_API_KEY和DASHVECTOR_ENDPOINT")
            return False

        logger.info(f"DashVector端点: {settings.DASHVECTOR_ENDPOINT}")
        logger.info(f"DashVector集合名称: {settings.DASHVECTOR_COLLECTION}")
        logger.info(f"DashVector命名空间: {settings.DASHVECTOR_NAMESPACE}")
        logger.info(f"向量维度: {settings.DASHVECTOR_COLLECTION_DIMENSION}")

        # 创建DashVector客户端
        client = dashvector.Client(
            api_key=settings.DASHVECTOR_API_KEY,
            endpoint=settings.DASHVECTOR_ENDPOINT
        )

        # 检查集合是否存在
        collection_name = settings.DASHVECTOR_COLLECTION
        logger.info(f"检查集合是否存在: {collection_name}")
        collection = client.get(collection_name)

        if collection:
            logger.info(f"集合存在，正在删除: {collection_name}")
            # 删除集合
            result = client.delete(collection_name)
            if result:
                logger.info(f"集合删除成功: {collection_name}")
            else:
                logger.error(f"集合删除失败: {collection_name}")
                return False
        else:
            logger.info(f"集合不存在: {collection_name}")

        # 创建新的集合
        logger.info(f"创建新的集合: {collection_name}")
        collection = client.create(
            name=collection_name,
            dimension=settings.DASHVECTOR_COLLECTION_DIMENSION,
            metric='cosine'  # 使用余弦相似度
        )

        if collection:
            logger.info(f"集合创建成功: {collection_name}")

            # 验证集合 - 尝试获取集合对象
            try:
                # 尝试获取集合对象以验证
                actual_collection = client.get(collection_name)
                if actual_collection:
                    logger.info(f"集合验证成功: {collection_name}")
                    # 尝试获取统计信息（如果可用）
                    try:
                        stats = actual_collection.stats()
                        logger.info(f"集合统计: 总文档数={stats.total_count}, 维度={stats.dimension}")
                    except AttributeError:
                        logger.info("无法获取集合统计信息（属性不可用）")
                else:
                    logger.warning(f"无法获取集合对象: {collection_name}")
            except Exception as e:
                logger.warning(f"集合验证时出错: {str(e)}")

            return True
        else:
            logger.error(f"集合创建失败: {collection_name}")
            return False

    except ImportError as e:
        logger.error(f"无法导入dashvector库: {e}")
        logger.error("请安装: pip install dashvector")
        return False
    except Exception as e:
        logger.error(f"重置DashVector失败: {str(e)}", exc_info=True)
        return False


async def main():
    """主函数"""
    logger.info("=== 开始强制重置DashVector向量库 ===")

    success = await reset_dashvector_collection()

    if success:
        logger.info("=== DashVector向量库重置成功 ===")
        return 0
    else:
        logger.error("=== DashVector向量库重置失败 ===")
        return 1


if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)