#!/usr/bin/env python3
"""
填充向量索引 - 为所有音频片段生成向量并添加到FAISS索引
"""

import asyncio
import sys
import pickle
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

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
from shared.models.user import User
from shared.models.chat import ChatMessage
from ai_models.nlp_service import get_text_vector
from services.search_service import search_service, add_audio_segment_to_index
from config import settings


async def get_db_session():
    """创建数据库会话（使用配置）"""
    # 从配置获取数据库URL，替换协议为asyncmy，替换localhost为mysql（容器内服务名）
    db_url = settings.DATABASE_URL.replace("mysql://", "mysql+asyncmy://")
    # 在Docker容器内，将localhost替换为mysql服务名
    if "localhost" in db_url:
        db_url = db_url.replace("localhost", "mysql")
    elif "127.0.0.1" in db_url:
        db_url = db_url.replace("127.0.0.1", "mysql")

    print(f"使用数据库URL: {db_url}")
    engine = create_async_engine(db_url, echo=False)  # 关闭echo以减少输出
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session


async def get_audio_segments(db: AsyncSession, limit: int = None) -> List[AudioSegment]:
    """获取音频片段列表"""
    stmt = select(AudioSegment).order_by(AudioSegment.created_at)
    if limit:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


async def generate_vector_for_segment(segment: AudioSegment) -> Tuple[List[float], int]:
    """为音频片段生成向量"""
    if not segment.transcription:
        print(f"片段 {segment.id[:8]}... 没有转录文本，跳过")
        return None, 0

    print(f"为片段 {segment.id[:8]}... 生成向量")
    print(f"  文本: {segment.transcription[:60]}...")

    # 获取文本向量
    vector = await get_text_vector(segment.transcription, text_type="document")
    if not vector:
        print(f"  错误: 无法生成向量")
        return None, 0

    vector_dimension = len(vector)
    print(f"  向量维度: {vector_dimension}")
    return vector, vector_dimension


async def update_segment_vector(db: AsyncSession, segment_id: str, vector: List[float], vector_dimension: int) -> bool:
    """更新数据库中的向量字段"""
    try:
        await db.execute(
            update(AudioSegment)
            .where(AudioSegment.id == segment_id)
            .values(
                vector=vector,
                vector_dimension=vector_dimension,
                vector_updated_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()
        print(f"  数据库向量字段已更新")
        return True
    except Exception as e:
        print(f"  更新数据库失败: {str(e)}")
        await db.rollback()
        return False


async def add_segment_to_index(segment_id: str, vector: List[float]) -> bool:
    """添加片段到FAISS索引"""
    try:
        # 直接调用search_service的add_segment_vector方法
        await search_service.add_segment_vector(segment_id, vector)
        print(f"  已添加到FAISS索引")
        return True
    except Exception as e:
        print(f"  添加到索引失败: {str(e)}")
        return False


async def check_existing_index() -> bool:
    """检查现有索引状态"""
    print("检查现有索引状态...")

    try:
        await search_service.initialize()
        stats = await search_service.get_index_stats()

        print(f"当前索引统计:")
        print(f"  总片段数: {stats['total_segments']}")
        print(f"  向量维度: {stats['vector_dimension']}")
        print(f"  segment_ids数量: {stats['segment_ids_count']}")
        print(f"  索引类型: {stats['index_type']}")

        return stats['total_segments'] > 0
    except Exception as e:
        print(f"检查索引状态失败: {str(e)}")
        return False


async def process_segments():
    """处理所有音频片段"""
    print("开始填充向量索引")
    print("=" * 60)

    # 检查现有索引
    has_existing_data = await check_existing_index()
    if has_existing_data:
        print("\n警告: 索引已有数据，是否继续？")
        print("继续操作将添加新数据，但不会删除现有数据")
        # 这里可以添加用户确认逻辑，现在默认继续

    # 获取数据库会话
    async_session = await get_db_session()
    async with async_session() as db:
        # 获取所有音频片段
        segments = await get_audio_segments(db)

        if not segments:
            print("错误: 没有找到音频片段")
            return False

        print(f"找到 {len(segments)} 个音频片段")

        processed_count = 0
        skipped_count = 0
        failed_count = 0

        for i, segment in enumerate(segments):
            print(f"\n[{i+1}/{len(segments)}] 处理片段 {segment.id[:8]}...")

            # 检查是否已有向量
            if segment.vector and segment.vector_dimension:
                print(f"  已有向量，维度: {segment.vector_dimension}")

                # 检查向量维度是否匹配配置
                if segment.vector_dimension == settings.VECTOR_DIMENSION:
                    print(f"  向量维度匹配配置({settings.VECTOR_DIMENSION})")

                    # 尝试添加到索引（如果尚未添加）
                    try:
                        await add_segment_to_index(segment.id, segment.vector)
                        processed_count += 1
                        continue
                    except Exception as e:
                        print(f"  添加到索引失败，重新生成向量: {str(e)}")
                else:
                    print(f"  向量维度不匹配配置({settings.VECTOR_DIMENSION} vs {segment.vector_dimension})，重新生成")

            # 生成新向量
            vector, vector_dimension = await generate_vector_for_segment(segment)
            if not vector:
                skipped_count += 1
                continue

            # 更新数据库
            db_success = await update_segment_vector(db, segment.id, vector, vector_dimension)
            if not db_success:
                failed_count += 1
                continue

            # 添加到索引
            index_success = await add_segment_to_index(segment.id, vector)
            if not index_success:
                failed_count += 1
                continue

            processed_count += 1

        print(f"\n处理完成:")
        print(f"  成功处理: {processed_count}")
        print(f"  跳过: {skipped_count}")
        print(f"  失败: {failed_count}")

        # 重新检查索引状态
        print("\n最终索引状态:")
        await check_existing_index()

        return processed_count > 0


async def verify_search():
    """验证搜索功能"""
    print("\n验证搜索功能...")

    async_session = await get_db_session()
    async with async_session() as db:
        # 测试搜索"现在几点了"
        from services.search_service import search_audio_segments_by_text

        query = "现在几点了"
        print(f"搜索查询: '{query}'")

        results = await search_audio_segments_by_text(
            query_text=query,
            top_k=5,
            similarity_threshold=0.3
        )

        print(f"找到 {len(results)} 个结果")

        if results:
            for i, (segment_id, similarity) in enumerate(results):
                # 获取片段详情
                stmt = select(AudioSegment).where(AudioSegment.id == segment_id)
                result = await db.execute(stmt)
                segment = result.scalar_one_or_none()

                if segment:
                    print(f"{i+1}. 片段ID: {segment_id[:8]}..., 相似度: {similarity:.4f}")
                    print(f"   文本: {segment.transcription[:80]}...")
                else:
                    print(f"{i+1}. 片段ID: {segment_id[:8]}..., 相似度: {similarity:.4f} (片段未找到)")

            return True
        else:
            print("未找到任何结果")
            return False


async def main():
    """主函数"""
    print("向量索引填充工具")
    print("=" * 60)

    try:
        # 填充索引
        success = await process_segments()

        if success:
            # 验证搜索
            print("\n" + "=" * 60)
            search_success = await verify_search()

            if search_success:
                print("\n索引填充和搜索验证完成!")
            else:
                print("\n索引填充完成，但搜索验证失败")
        else:
            print("\n索引填充失败")

        # 检查索引文件
        print("\n索引文件检查:")
        index_path = Path(settings.FAISS_INDEX_PATH)
        metadata_path = index_path.with_suffix('.pkl')

        print(f"FAISS索引文件: {index_path}")
        if index_path.exists():
            size = index_path.stat().st_size
            print(f"  大小: {size} 字节 ({size/1024:.2f} KB)")
        else:
            print("  不存在")

        print(f"元数据文件: {metadata_path}")
        if metadata_path.exists():
            size = metadata_path.stat().st_size
            print(f"  大小: {size} 字节 ({size/1024:.2f} KB)")

            # 尝试加载元数据
            try:
                with open(metadata_path, 'rb') as f:
                    metadata = pickle.load(f)
                print(f"  元数据内容: {metadata}")
            except Exception as e:
                print(f"  加载元数据失败: {str(e)}")
        else:
            print("  不存在")

        return 0 if success else 1

    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))