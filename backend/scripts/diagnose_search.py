#!/usr/bin/env python3
"""
诊断搜索和匹配问题
"""

import sys
import os
from pathlib import Path

# 设置项目根目录
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from config import settings


async def diagnose():
    print("=" * 70)
    print("搜索系统诊断")
    print("=" * 70)

    print(f"\n1. 配置检查:")
    print(f"   AUDIO_REPLY_THRESHOLD: {settings.AUDIO_REPLY_THRESHOLD}")
    print(f"   AUDIO_SUGGEST_THRESHOLD: {settings.AUDIO_SUGGEST_THRESHOLD}")
    print(f"   SIMILARITY_THRESHOLD: {settings.SIMILARITY_THRESHOLD}")
    print(f"   VECTOR_DIMENSION: {settings.VECTOR_DIMENSION}")

    # 2. 检查向量索引状态
    print(f"\n2. 向量索引状态:")
    from services.search_service import search_service
    await search_service.initialize()
    stats = await search_service.get_index_stats()
    print(f"   引擎: {stats.get('engine')}")
    print(f"   总片段数: {stats.get('total_segments')}")
    print(f"   向量维度: {stats.get('vector_dimension')}")

    if stats.get('total_segments', 0) == 0:
        print(f"\n   ❌ 向量索引为空！这是问题所在。")
        return

    # 3. 测试向量搜索
    print(f"\n3. 向量搜索测试:")
    test_queries = [
        "你吃了么",
        "今天天气",
        "大家好",
        "谢谢",
    ]

    for query in test_queries:
        results = await search_service.search_by_text(
            query_text=query,
            top_k=3,
            similarity_threshold=0.0  # 获取所有结果
        )
        print(f"\n   查询 '{query}':")
        if results:
            for segment_id, similarity in results:
                status = "✅" if similarity >= settings.AUDIO_REPLY_THRESHOLD else "❌"
                print(f"     {status} {segment_id}: {similarity:.4f}")
        else:
            print(f"     无结果")

    # 4. 检查数据库中的语弹
    print(f"\n4. 数据库语弹检查:")

    # 直接查询数据库
    import aiomysql
    try:
        conn = await aiomysql.connect(
            host='soundverse-mysql',
            port=3306,
            user='soundverse',
            password='password',
            db='soundverse'
        )

        async with conn.cursor() as cur:
            # 统计语弹数量
            await cur.execute("SELECT COUNT(*) FROM audio_segments WHERE review_status = 'approved'")
            count = await cur.fetchone()
            print(f"   已审核语弹数: {count[0]}")

            # 获取几个示例
            await cur.execute("""
                SELECT id, transcription, source_title
                FROM audio_segments
                WHERE review_status = 'approved' AND transcription IS NOT NULL
                ORDER BY RAND()
                LIMIT 3
            """)
            rows = await cur.fetchall()

            print(f"\n   示例语弹:")
            for row in rows:
                print(f"     ID: {row[0][:8]}...")
                print(f"     文本: {row[1][:50]}..." if row[1] and len(row[1]) > 50 else f"     文本: {row[1]}")
                print(f"     来源: {row[2]}")
                print()

        conn.close()
    except Exception as e:
        print(f"   数据库查询失败: {e}")

    # 5. 检查向量索引和数据库的一致性
    print(f"\n5. 一致性检查:")
    total_in_index = stats.get('total_segments', 0)

    try:
        conn = await aiomysql.connect(
            host='soundverse-mysql',
            port=3306,
            user='soundverse',
            password='password',
            db='soundverse'
        )

        async with conn.cur() as cur:
            await cur.execute("SELECT COUNT(*) FROM audio_segments WHERE review_status = 'approved'")
            count = await cur.fetchone()
            total_in_db = count[0]

            print(f"   向量索引中的片段数: {total_in_index}")
            print(f"   数据库中的语弹数: {total_in_db}")

            if total_in_index != total_in_db:
                print(f"   ⚠️ 数量不一致！可能需要重新同步向量索引。")
            else:
                print(f"   ✅ 数量一致")

        conn.close()
    except Exception as e:
        print(f"   检查失败: {e}")

    print(f"\n" + "=" * 70)
    print("诊断结论")
    print("=" * 70)

    if stats.get('total_segments', 0) == 0:
        print("\n❌ 向量索引为空，需要重新构建索引！")
        print("   解决方案: 运行向量同步脚本")
    elif stats.get('total_segments', 0) < 10:
        print(f"\n⚠️ 向量索引中片段数较少 ({stats.get('total_segments')})")
        print("   可能影响搜索效果")
    else:
        print(f"\n✅ 向量索引正常，包含 {stats.get('total_segments')} 个片段")


if __name__ == "__main__":
    asyncio.run(diagnose())
