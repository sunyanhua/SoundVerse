#!/usr/bin/env python3
"""
清理已删除音频源的残留数据

测试脚本 - 用于数据清理验证
存放位置: test/scripts/ (符合测试管理制度)
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.audio import AudioSource, AudioSegment
from services.storage_service import StorageService
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cleanup_deleted_sources(dry_run: bool = True):
    """
    清理已标记为 deleted 的音频源

    Args:
        dry_run: 如果为 True，只打印日志不执行实际删除
    """
    # 确保数据库已初始化
    import shared.database.session as db_session
    await db_session.init_db()

    async with db_session.async_session_maker() as db:
        # 1. 查找所有标记为 deleted 的音频源
        stmt = select(AudioSource).where(AudioSource.processing_status == "deleted")
        result = await db.execute(stmt)
        deleted_sources = result.scalars().all()

        if not deleted_sources:
            logger.info("没有找到标记为 deleted 的音频源")
            return

        logger.info(f"找到 {len(deleted_sources)} 个标记为 deleted 的音频源")

        if dry_run:
            logger.info("[干运行模式] 不执行实际删除，仅显示将要执行的操作")
            for source in deleted_sources:
                logger.info(f"  - {source.id}: {source.title}")
            return

        storage_service = StorageService()
        total_segments = 0
        errors = []

        for source in deleted_sources:
            logger.info(f"\n处理音频源: {source.id} - {source.title}")

            # 2. 查找关联的语弹片段
            stmt_segments = select(AudioSegment).where(AudioSegment.source_id == source.id)
            result_segments = await db.execute(stmt_segments)
            segments = result_segments.scalars().all()

            logger.info(f"  关联语弹数量: {len(segments)}")

            # 3. 清理语弹
            for segment in segments:
                try:
                    # 删除向量索引
                    if not dry_run:
                        try:
                            from services.search_service import delete_segment_from_index
                            await delete_segment_from_index(str(segment.id))
                            logger.info(f"  删除向量索引: {segment.id}")
                        except Exception as e:
                            logger.warning(f"  删除向量索引失败: {segment.id}, {e}")
                            errors.append(f"向量索引: {segment.id}")

                    # 删除语弹 OSS 文件
                    if segment.oss_key and not dry_run:
                        try:
                            await storage_service.delete_file(segment.oss_key)
                            logger.info(f"  删除语弹 OSS: {segment.oss_key}")
                        except Exception as e:
                            logger.warning(f"  删除语弹 OSS 失败: {segment.oss_key}, {e}")
                            errors.append(f"语弹OSS: {segment.oss_key}")

                    # 删除数据库记录
                    if not dry_run:
                        await db.delete(segment)

                    total_segments += 1

                except Exception as e:
                    logger.error(f"  删除语弹失败: {segment.id}, {e}")
                    errors.append(f"语弹: {segment.id}")

            # 4. 删除音频源 OSS 文件
            if source.oss_key and not dry_run:
                try:
                    await storage_service.delete_file(source.oss_key)
                    logger.info(f"  删除音频源 OSS: {source.oss_key}")
                except Exception as e:
                    logger.warning(f"  删除音频源 OSS 失败: {source.oss_key}, {e}")
                    errors.append(f"音频源OSS: {source.oss_key}")

            # 5. 删除音频源数据库记录
            if not dry_run:
                await db.delete(source)
                logger.info(f"  删除音频源记录: {source.id}")

        # 6. 提交事务
        if not dry_run:
            await db.commit()
            logger.info(f"\n清理完成: 删除了 {len(deleted_sources)} 个音频源, {total_segments} 个语弹")
        else:
            logger.info(f"\n干运行完成: 将要删除 {len(deleted_sources)} 个音频源")

        if errors:
            logger.warning(f"清理过程中出现 {len(errors)} 个错误")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='清理已删除的音频源残留数据')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='干运行模式，只显示将要执行的操作')
    parser.add_argument('--force', '-f', action='store_true',
                        help='强制执行删除（非干运行模式）')

    args = parser.parse_args()

    if args.dry_run:
        asyncio.run(cleanup_deleted_sources(dry_run=True))
    elif args.force:
        confirm = input("确认要执行实际删除操作吗？此操作不可恢复！\n输入 'yes' 继续: ")
        if confirm.lower() == 'yes':
            asyncio.run(cleanup_deleted_sources(dry_run=False))
        else:
            logger.info("操作已取消")
    else:
        logger.info("默认使用干运行模式，使用 --force 参数执行实际删除")
        asyncio.run(cleanup_deleted_sources(dry_run=True))


if __name__ == "__main__":
    main()
