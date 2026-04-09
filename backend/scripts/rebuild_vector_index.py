#!/usr/bin/env python3
"""
重建向量索引 - 将数据库中所有语弹重新添加到向量索引
"""

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from config import settings


async def rebuild_index():
    print("=" * 70)
    print("重建向量索引")
    print("=" * 70)

    # 初始化服务
    from services.search_service import search_service
    from ai_models.nlp_service import get_text_vector

    await search_service.initialize()

    # 查询数据库中的所有语弹
    import aiomysql

    conn = await aiomysql.connect(
        host='soundverse-mysql',
        port=3306,
        user='soundverse',
        password='password',
        db='soundverse'
    )

    async with conn.cursor() as cur:
        await cur.execute("""
            SELECT id, transcription
            FROM audio_segments
            WHERE review_status = 'approved'
            AND transcription IS NOT NULL
            AND transcription != ''
        """)

        rows = await cur.fetchall()

        print(f"\n找到 {len(rows)} 个语弹需要添加到向量索引")

        success_count = 0
        fail_count = 0

        for i, (segment_id, transcription) in enumerate(rows):
            print(f"\n[{i+1}/{len(rows)}] 处理语弹: {segment_id[:8]}...")
            print(f"  文本: {transcription[:50]}..." if len(transcription) > 50 else f"  文本: {transcription}")

            try:
                # 获取向量
                vector = await get_text_vector(transcription, text_type="document")

                if vector:
                    # 添加到索引
                    await search_service.add_segment_vector(segment_id, vector)
                    print(f"  ✅ 成功添加向量 ({len(vector)} 维)")
                    success_count += 1
                else:
                    print(f"  ❌ 无法获取向量")
                    fail_count += 1

            except Exception as e:
                print(f"  ❌ 错误: {e}")
                fail_count += 1

    conn.close()

    # 显示最终统计
    print(f"\n{'='*70}")
    print("重建完成")
    print(f"{'='*70}")

    stats = await search_service.get_index_stats()
    print(f"\n向量索引统计:")
    print(f"  引擎: {stats.get('engine')}")
    print(f"  总片段数: {stats.get('total_segments')}")

    print(f"\n处理结果:")
    print(f"  成功: {success_count}")
    print(f"  失败: {fail_count}")


if __name__ == "__main__":
    asyncio.run(rebuild_index())
