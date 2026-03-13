#!/usr/bin/env python3
"""
清理烂尾数据脚本：删除片段数少于50条的音频源及其片段
"""
import asyncio
import sys
import os
import logging
from pathlib import Path
import argparse

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 使用Docker容器内的默认MySQL连接
if os.environ.get("DATABASE_URL") is None:
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select, func, text, delete
from sqlalchemy.orm import selectinload
from shared.models.audio import AudioSource, AudioSegment
from shared.models.user import User
from services.search_service import search_service
import shared.database.session as db_session

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_stalled_sources(threshold: int = 50) -> list:
    """
    获取片段数少于阈值的音频源

    返回: 列表，每个元素是 (source_id, title, filename, segment_count)
    """
    logger.info(f"查找片段数少于 {threshold} 的音频源...")

    async with db_session.async_session_maker() as session:
        # 使用原始SQL查询避免ORM关系初始化问题
        # 查询所有音频源及其片段数量
        sql = """
        SELECT
            s.id,
            s.title,
            s.original_filename,
            COUNT(seg.id) as segment_count
        FROM audio_sources s
        LEFT JOIN audio_segments seg ON s.id = seg.source_id
        GROUP BY s.id, s.title, s.original_filename
        HAVING COUNT(seg.id) < :threshold
        ORDER BY COUNT(seg.id) ASC
        """

        result = await session.execute(text(sql), {"threshold": threshold})
        stalled_sources = result.fetchall()

        # 查询没有任何片段的音频源
        sql_no_segments = """
        SELECT
            s.id,
            s.title,
            s.original_filename
        FROM audio_sources s
        WHERE NOT EXISTS (
            SELECT 1 FROM audio_segments seg WHERE seg.source_id = s.id
        )
        """

        result_no_segments = await session.execute(text(sql_no_segments))
        no_segment_sources = [(row.id, row.title, row.original_filename, 0) for row in result_no_segments]

        # 合并结果
        all_stalled = []
        for row in stalled_sources:
            all_stalled.append((row.id, row.title, row.original_filename, row.segment_count))

        all_stalled.extend(no_segment_sources)

        logger.info(f"找到 {len(all_stalled)} 个烂尾音频源 (片段数 < {threshold})")

        # 打印详细信息
        if all_stalled:
            logger.info("烂尾音频源列表:")
            logger.info("-" * 120)
            logger.info(f"{'序号':<5} {'源ID':<36} {'标题':<30} {'文件名':<30} {'片段数':<10}")
            logger.info("-" * 120)
            for i, (source_id, title, filename, segment_count) in enumerate(all_stalled, 1):
                title_display = title[:28] + '..' if len(title) > 30 else title
                filename_display = filename[:28] + '..' if len(filename) > 30 else filename
                logger.info(f"{i:<5} {source_id:<36} {title_display:<30} {filename_display:<30} {segment_count:<10}")
            logger.info("-" * 120)

        return all_stalled


async def delete_stalled_sources(stalled_sources: list, confirm: bool = True) -> dict:
    """
    删除烂尾音频源及其片段

    返回: 统计信息字典
    """
    if not stalled_sources:
        logger.info("没有需要删除的烂尾音频源")
        return {'sources_deleted': 0, 'segments_deleted': 0, 'dashvector_deleted': 0}

    total_sources = len(stalled_sources)
    total_segments = sum(segment_count for _, _, _, segment_count in stalled_sources)

    logger.info(f"准备删除 {total_sources} 个音频源，共计 {total_segments} 个片段")

    if confirm:
        logger.warning("⚠️  确认要删除这些数据吗？此操作不可恢复！")
        logger.warning("   请在5秒内按 Ctrl+C 取消...")
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("操作已取消")
            return {'sources_deleted': 0, 'segments_deleted': 0, 'dashvector_deleted': 0}

    sources_deleted = 0
    segments_deleted = 0
    dashvector_deleted = 0

    # 删除向量索引中的对应片段
    try:
        await search_service.initialize()
        logger.info("开始从DashVector删除烂尾音频源的片段...")

        for source_id, _, _, segment_count in stalled_sources:
            if segment_count == 0:
                continue

            # 获取该源的所有片段ID
            async with db_session.async_session_maker() as session:
                stmt = select(AudioSegment.id).where(AudioSegment.source_id == source_id)
                result = await session.execute(stmt)
                segment_ids = [row[0] for row in result]

                # 从DashVector删除
                for segment_id in segment_ids:
                    try:
                        await search_service.delete_document(segment_id)
                        dashvector_deleted += 1
                    except Exception as e:
                        logger.warning(f"从DashVector删除片段 {segment_id} 失败: {str(e)}")

        logger.info(f"从DashVector删除了 {dashvector_deleted} 个片段向量")
    except Exception as e:
        logger.error(f"清理DashVector失败: {str(e)}")

    # 删除数据库中的片段和源
    logger.info("开始删除数据库中的烂尾数据...")

    engine = create_async_engine(os.environ["DATABASE_URL"])

    async with engine.begin() as conn:
        # 禁用外键检查
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        try:
            # 先删除片段
            for source_id, _, _, segment_count in stalled_sources:
                if segment_count == 0:
                    continue

                # 删除该源的所有片段
                stmt = delete(AudioSegment).where(AudioSegment.source_id == source_id)
                result = await conn.execute(stmt)
                deleted_segments = result.rowcount
                segments_deleted += deleted_segments
                logger.info(f"删除源 {source_id}: 删除了 {deleted_segments} 个片段")

            # 再删除音频源
            for source_id, title, filename, _ in stalled_sources:
                stmt = delete(AudioSource).where(AudioSource.id == source_id)
                result = await conn.execute(stmt)
                if result.rowcount > 0:
                    sources_deleted += 1
                    logger.info(f"删除音频源: {title} ({filename})")

        finally:
            # 重新启用外键检查
            await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    logger.info(f"数据库删除完成: 删除了 {sources_deleted} 个音频源, {segments_deleted} 个片段")

    return {
        'sources_deleted': sources_deleted,
        'segments_deleted': segments_deleted,
        'dashvector_deleted': dashvector_deleted
    }


async def get_database_stats() -> dict:
    """获取数据库统计信息"""
    async with db_session.async_session_maker() as session:
        # 音频源总数
        result = await session.execute(select(func.count()).select_from(AudioSource))
        total_sources = result.scalar() or 0

        # 音频片段总数
        result = await session.execute(select(func.count()).select_from(AudioSegment))
        total_segments = result.scalar() or 0

        # 已审核的片段数量
        result = await session.execute(
            select(func.count()).select_from(AudioSegment).where(AudioSegment.review_status == "approved")
        )
        approved_segments = result.scalar() or 0

        return {
            'total_sources': total_sources,
            'total_segments': total_segments,
            'approved_segments': approved_segments
        }


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="清理烂尾音频数据脚本")
    parser.add_argument(
        "--threshold",
        type=int,
        default=50,
        help="片段数阈值，少于这个数的音频源将被视为烂尾（默认: 50）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干运行模式，只查找烂尾源但不实际删除"
    )
    parser.add_argument(
        "--no-confirm",
        action="store_true",
        help="跳过确认提示，直接删除（谨慎使用！）"
    )

    args = parser.parse_args()

    logger.info("=== 清理烂尾音频数据开始 ===")
    logger.info(f"阈值: {args.threshold} 个片段")
    logger.info(f"干运行模式: {args.dry_run}")
    logger.info(f"跳过确认: {args.no_confirm}")

    try:
        # 初始化数据库
        await db_session.init_db()

        # 初始化搜索服务
        try:
            await search_service.initialize()
            logger.info("搜索服务初始化完成")
        except Exception as e:
            logger.warning(f"搜索服务初始化失败: {str(e)}")

        # 处理前统计
        stats_before = await get_database_stats()
        logger.info(f"处理前数据库统计:")
        logger.info(f"  - 音频源总数: {stats_before['total_sources']}")
        logger.info(f"  - 音频片段总数: {stats_before['total_segments']}")
        logger.info(f"  - 已审核片段数: {stats_before['approved_segments']}")

        # 查找烂尾音频源
        stalled_sources = await get_stalled_sources(args.threshold)

        if not stalled_sources:
            logger.info("没有找到烂尾音频源，退出")
            return 0

        # 计算烂尾数据统计
        stalled_segment_count = sum(segment_count for _, _, _, segment_count in stalled_sources)
        logger.info(f"烂尾数据统计: {len(stalled_sources)} 个音频源, {stalled_segment_count} 个片段")

        # 干运行模式：只显示不删除
        if args.dry_run:
            logger.info("干运行模式：只显示烂尾数据，不实际删除")
            logger.info("=== 干运行完成 ===")
            return 0

        # 实际删除操作
        delete_stats = await delete_stalled_sources(
            stalled_sources,
            confirm=not args.no_confirm
        )

        # 处理后统计
        stats_after = await get_database_stats()
        logger.info(f"处理后数据库统计:")
        logger.info(f"  - 音频源总数: {stats_after['total_sources']} (减少: {stats_before['total_sources'] - stats_after['total_sources']})")
        logger.info(f"  - 音频片段总数: {stats_after['total_segments']} (减少: {stats_before['total_segments'] - stats_after['total_segments']})")
        logger.info(f"  - 已审核片段数: {stats_after['approved_segments']}")

        # 验证删除结果
        expected_segment_decrease = stalled_segment_count
        actual_segment_decrease = stats_before['total_segments'] - stats_after['total_segments']

        if actual_segment_decrease == expected_segment_decrease:
            logger.info(f"✅ 片段删除验证通过: 预期减少 {expected_segment_decrease}, 实际减少 {actual_segment_decrease}")
        else:
            logger.warning(f"⚠️  片段删除验证不一致: 预期减少 {expected_segment_decrease}, 实际减少 {actual_segment_decrease}")

        # DashVector删除统计
        if delete_stats['dashvector_deleted'] > 0:
            logger.info(f"DashVector清理: 删除了 {delete_stats['dashvector_deleted']} 个向量")

        logger.info("=== 烂尾数据清理完成 ===")

    except KeyboardInterrupt:
        logger.info("操作被用户中断")
        return 1
    except Exception as e:
        logger.error(f"清理过程中发生错误: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)