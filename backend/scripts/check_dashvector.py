#!/usr/bin/env python3
"""
检查DashVector状态
"""
import os
import sys
import logging
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 设置环境变量
os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

import dashvector
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_dashvector():
    """Check DashVector status"""
    print("=== Check DashVector Status ===")

    # Check config
    print(f"1. DashVector Config Check:")
    print(f"   - DASHVECTOR_API_KEY: {'Set' if settings.DASHVECTOR_API_KEY else 'Not set'}")
    print(f"   - DASHVECTOR_ENDPOINT: {'Set' if settings.DASHVECTOR_ENDPOINT else 'Not set'}")
    print(f"   - DASHVECTOR_NAMESPACE: {settings.DASHVECTOR_NAMESPACE}")
    print(f"   - DASHVECTOR_COLLECTION: {settings.DASHVECTOR_COLLECTION}")
    print(f"   - DASHVECTOR_COLLECTION_DIMENSION: {settings.DASHVECTOR_COLLECTION_DIMENSION}")
    print(f"   - DASHSCOPE_EMBEDDING_MODEL: {settings.DASHSCOPE_EMBEDDING_MODEL}")
    print(f"   - VECTOR_DIMENSION: {settings.VECTOR_DIMENSION}")

    # Check dimension consistency
    if settings.DASHVECTOR_COLLECTION_DIMENSION == settings.VECTOR_DIMENSION:
        print(f"   OK Vector dimension consistent: {settings.VECTOR_DIMENSION}")
    else:
        print(f"   ERROR Vector dimension mismatch: DashVector={settings.DASHVECTOR_COLLECTION_DIMENSION}, VECTOR_DIMENSION={settings.VECTOR_DIMENSION}")

    if not settings.DASHVECTOR_API_KEY or not settings.DASHVECTOR_ENDPOINT:
        print("⚠️  DashVector配置不完整，跳过连接测试")
        return

    try:
        # 创建DashVector客户端
        print(f"\n2. 连接DashVector...")
        client = dashvector.Client(
            api_key=settings.DASHVECTOR_API_KEY,
            endpoint=settings.DASHVECTOR_ENDPOINT
        )
        print(f"   ✓ DashVector客户端创建成功")

        # 获取集合
        collection_name = settings.DASHVECTOR_COLLECTION
        print(f"\n3. 获取集合 '{collection_name}'...")
        collection = client.get(collection_name)

        if collection:
            print(f"   ✓ 集合存在")

            try:
                # 获取统计信息
                stats = collection.stats()
                print(f"\n4. 集合统计信息:")
                print(f"   - 文档数量: {stats.doc_count}")
                print(f"   - 向量维度: {stats.dimension}")
                print(f"   - 全量文档数量: {stats.full_doc_count}")

                # 检查维度
                if stats.dimension == settings.VECTOR_DIMENSION:
                    print(f"   ✓ 集合维度与配置一致: {stats.dimension}")
                else:
                    print(f"   ✗ 集合维度不一致: 集合={stats.dimension}, 配置={settings.VECTOR_DIMENSION}")

                # 获取一些样本
                if stats.doc_count > 0:
                    print(f"\n5. 获取样本数据...")
                    try:
                        result = collection.query(limit=3)
                        if result and hasattr(result, 'docs') and result.docs:
                            print(f"   找到 {len(result.docs)} 个文档:")
                            for i, doc in enumerate(result.docs[:2], 1):  # 只显示前两个
                                print(f"   - 文档{i}: ID={doc.id[:20]}..., 向量长度={len(doc.vector)}")
                        else:
                            print(f"   无法获取样本文档")
                    except Exception as e:
                        print(f"   查询样本失败: {e}")
                else:
                    print(f"   ⚠️ 集合为空，无文档")

            except Exception as e:
                print(f"   获取集合统计失败: {e}")

        else:
            print(f"   ⚠️ 集合不存在")

    except Exception as e:
        print(f"\n✗ DashVector连接失败: {e}")
        import traceback
        traceback.print_exc()

def check_database_vectors():
    """检查数据库中的向量"""
    print(f"\n=== 检查数据库向量状态 ===")

    import asyncio
    from sqlalchemy import select, func
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from shared.models.audio import AudioSegment
    from shared.models.user import User
    from shared.models.chat import ChatMessage

    async def async_check():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as db:
            # 统计总数
            stmt_total = select(func.count()).select_from(AudioSegment)
            result = await db.execute(stmt_total)
            total = result.scalar()
            print(f"1. 音频片段总数: {total}")

            # 有向量的片段
            stmt_with_vector = select(func.count()).select_from(AudioSegment).where(
                AudioSegment.vector.is_not(None)
            )
            result = await db.execute(stmt_with_vector)
            with_vector = result.scalar()
            print(f"2. 有向量的片段: {with_vector} ({with_vector/total*100:.1f}%)")

            # 已审核通过的片段
            stmt_approved = select(func.count()).select_from(AudioSegment).where(
                AudioSegment.review_status == "approved"
            )
            result = await db.execute(stmt_approved)
            approved = result.scalar()
            print(f"3. 已审核通过的片段: {approved} ({approved/total*100:.1f}%)")

            # 有向量且已审核的片段
            stmt_approved_vector = select(func.count()).select_from(AudioSegment).where(
                AudioSegment.review_status == "approved",
                AudioSegment.vector.is_not(None)
            )
            result = await db.execute(stmt_approved_vector)
            approved_vector = result.scalar()
            print(f"4. 有向量且已审核的片段: {approved_vector} ({approved_vector/total*100:.1f}%)")

            # 获取一些有向量的样本
            if approved_vector > 0:
                print(f"\n5. 有向量片段的样本:")
                stmt_samples = select(AudioSegment).where(
                    AudioSegment.review_status == "approved",
                    AudioSegment.vector.is_not(None),
                    AudioSegment.transcription.is_not(None)
                ).limit(3)
                result = await db.execute(stmt_samples)
                segments = result.scalars().all()

                for i, seg in enumerate(segments, 1):
                    text_preview = seg.transcription[:50] + ("..." if len(seg.transcription) > 50 else "")
                    vector_dim = seg.vector_dimension if seg.vector_dimension else "未知"
                    print(f"   - 样本{i}: ID={seg.id[:12]}..., 转录='{text_preview}', 向量维度={vector_dim}")

    asyncio.run(async_check())

if __name__ == "__main__":
    check_dashvector()
    check_database_vectors()