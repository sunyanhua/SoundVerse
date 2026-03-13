#!/usr/bin/env python3
"""
DashVector 同步脚本 - 将所有音频片段向量同步到DashVector
"""
import asyncio
import sys
import numpy as np
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 模拟 audio_processing_service 模块以避免 pyaudioop 导入
import sys
sys.modules['services.audio_processing_service'] = type(sys)('audio_processing_service')
sys.modules['services.audio_processing_service'].audio_processing_service = object()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, update
from shared.models.audio import AudioSegment
from shared.models.user import User  # 解决SQLAlchemy映射问题
from shared.models.chat import ChatMessage
from services.search_service import search_service
from config import settings


async def get_db_session():
    """创建数据库会话"""
    db_url = settings.DATABASE_URL.replace("mysql://", "mysql+asyncmy://")
    if "localhost" in db_url:
        db_url = db_url.replace("localhost", "mysql")
    elif "127.0.0.1" in db_url:
        db_url = db_url.replace("127.0.0.1", "mysql")

    print(f"使用数据库URL: {db_url}")
    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session


async def verify_vector_quality(vector):
    """验证向量质量：维度和模长"""
    if not vector:
        return False, "向量为空"

    dimension = len(vector)
    if dimension != settings.VECTOR_DIMENSION:
        return False, f"维度不匹配: {dimension} != {settings.VECTOR_DIMENSION}"

    # 计算模长（L2范数）
    norm = sum(v*v for v in vector) ** 0.5
    # 检查模长是否接近1.0（余弦相似度向量通常被归一化）
    if abs(norm - 1.0) > 0.01:
        return False, f"模长偏离1.0: {norm:.6f}"

    return True, f"维度: {dimension}, 模长: {norm:.6f}"


async def sync_to_dashvector():
    """同步所有向量到DashVector"""
    print("DashVector 同步工具")
    print("=" * 60)

    # 初始化search_service（确保使用DashVector）
    await search_service.initialize()
    print(f"使用引擎: {'DashVector' if search_service.use_dashvector else 'FAISS'}")
    print(f"DashVector集合: {search_service.dashvector_collection is not None}")

    # 获取数据库会话
    async_session = await get_db_session()
    async with async_session() as db:
        # 获取所有有向量的音频片段
        stmt = select(AudioSegment).where(
            AudioSegment.vector.is_not(None),
            AudioSegment.vector_dimension == settings.VECTOR_DIMENSION
        ).order_by(AudioSegment.created_at)

        result = await db.execute(stmt)
        segments = result.scalars().all()

        if not segments:
            print("错误: 没有找到有向量的音频片段")
            return False

        print(f"找到 {len(segments)} 个有向量的音频片段")

        success_count = 0
        failed_count = 0
        quality_failed_count = 0

        for i, segment in enumerate(segments):
            print(f"\n[{i+1}/{len(segments)}] 处理片段 {segment.id[:8]}...")

            # 验证向量质量
            valid, msg = await verify_vector_quality(segment.vector)
            if not valid:
                print(f"  向量质量验证失败: {msg}")
                quality_failed_count += 1
                continue

            print(f"  向量质量验证通过: {msg}")

            # 添加到DashVector
            try:
                await search_service.add_segment_vector(segment.id, segment.vector)
                print(f"  已添加到DashVector")
                success_count += 1
            except Exception as e:
                print(f"  添加到DashVector失败: {str(e)}")
                failed_count += 1

        print(f"\n同步完成:")
        print(f"  成功: {success_count}")
        print(f"  质量验证失败: {quality_failed_count}")
        print(f"  DashVector插入失败: {failed_count}")

        return success_count > 0


async def check_dashvector_stats():
    """检查DashVector统计信息"""
    print("\n" + "=" * 60)
    print("检查DashVector统计信息...")

    stats = await search_service.get_index_stats()
    print(f"当前索引统计:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    total_docs = stats.get('total_segments', 0)
    print(f"\nDashVector中的总文档数: {total_docs}")

    return total_docs


async def main():
    """主函数"""
    try:
        # 同步到DashVector
        success = await sync_to_dashvector()

        if success:
            # 检查统计信息
            total_docs = await check_dashvector_stats()

            # 验证搜索功能
            print("\n" + "=" * 60)
            print("验证搜索功能...")

            query_text = "现在几点了"
            results = await search_service.search_by_text(
                query_text=query_text,
                top_k=3,
                similarity_threshold=0.3
            )

            print(f"搜索查询: '{query_text}'")
            print(f"找到 {len(results)} 个结果")
            if results:
                for i, (segment_id, similarity) in enumerate(results):
                    print(f"{i+1}. 片段ID: {segment_id[:8]}..., 相似度: {similarity:.4f}")

            print(f"\nDashVector同步完成! 总文档数: {total_docs}")

            # 判断是否符合用户期望
            if total_docs == 99 or total_docs == 100:
                print("✅ 符合预期: total_docs 等于 99 或 100")
            else:
                print(f"⚠️  注意: total_docs ({total_docs}) 不等于 99 或 100")

            return 0
        else:
            print("\nDashVector同步失败")
            return 1

    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))