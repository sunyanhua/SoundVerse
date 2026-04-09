#!/usr/bin/env python3
"""
从数据库中随机选择语弹，设计一定能匹配的提问词
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
from ai_models.nlp_service import get_text_vector, nlp_service


async def get_random_segment():
    """从数据库中获取随机语弹"""
    from shared.database import async_session
    from sqlalchemy import select, func
    from shared.models.audio import AudioSegment

    async with async_session() as db:
        # 获取已审核通过的语弹
        stmt = select(AudioSegment).where(
            AudioSegment.review_status == "approved",
            AudioSegment.transcription != None,
            AudioSegment.transcription != ""
        ).order_by(func.random()).limit(1)

        result = await db.execute(stmt)
        segment = result.scalar_one_or_none()
        return segment


async def test_similarity(query: str, document: str):
    """测试两个文本的相似度"""
    # 获取向量
    query_vector = await get_text_vector(query, text_type="query")
    doc_vector = await get_text_vector(document, text_type="document")

    if not query_vector or not doc_vector:
        return 0.0

    # 计算相似度
    similarity = await nlp_service.calculate_similarity(query_vector, doc_vector)
    return similarity


async def main():
    print("=" * 70)
    print("寻找测试用例 - 保证能匹配到的语弹和提问词")
    print("=" * 70)

    print(f"\n当前阈值配置:")
    print(f"  SIMILARITY_THRESHOLD:    {settings.SIMILARITY_THRESHOLD}")
    print(f"  AUDIO_SUGGEST_THRESHOLD: {settings.AUDIO_SUGGEST_THRESHOLD}")
    print(f"  AUDIO_REPLY_THRESHOLD:   {settings.AUDIO_REPLY_THRESHOLD}")

    # 获取随机语弹
    print("\n正在从数据库获取语弹...")
    segment = await get_random_segment()

    if not segment:
        print("❌ 没有找到可用的语弹")
        return

    print(f"\n{'='*70}")
    print(f"选中语弹:")
    print(f"{'='*70}")
    print(f"ID: {segment.id}")
    print(f"文本: {segment.transcription}")
    print(f"时长: {segment.duration:.2f}秒")
    print(f"来源: {segment.source_title}")

    # 策略1: 使用语弹中的关键词作为提问词
    transcription = segment.transcription
    words = transcription.split()

    print(f"\n{'='*70}")
    print("测试不同的提问策略:")
    print(f"{'='*70}")

    test_queries = []

    # 策略1: 提取长词组(2-4个字)
    for i in range(len(words)):
        for j in range(i+1, min(i+5, len(words)+1)):
            phrase = ''.join(words[i:j])
            if len(phrase) >= 2 and len(phrase) <= 8:
                test_queries.append(("关键词提取", phrase))

    # 策略2: 完整句子
    if len(transcription) <= 20:
        test_queries.append(("完整句子", transcription))
    else:
        # 取前20个字符
        test_queries.append(("句子前半", transcription[:20]))
        # 取后20个字符
        test_queries.append(("句子后半", transcription[-20:]))

    # 策略3: 包含关系
    if len(transcription) > 4:
        test_queries.append(("包含子串", transcription[2:10]))

    # 去重
    unique_queries = []
    seen = set()
    for strategy, query in test_queries:
        if query not in seen:
            seen.add(query)
            unique_queries.append((strategy, query))

    # 测试前20个不同的提问词
    best_match = None
    best_similarity = 0.0

    for strategy, query in unique_queries[:20]:
        similarity = await test_similarity(query, transcription)
        status = "✅" if similarity >= settings.AUDIO_REPLY_THRESHOLD else "❌"
        print(f"\n{status} [{strategy}] '{query}'")
        print(f"   相似度: {similarity:.4f}")

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (strategy, query)

    # 输出最佳匹配
    if best_match:
        print(f"\n{'='*70}")
        print("推荐测试用例 (最高相似度):")
        print(f"{'='*70}")
        print(f"\n📌 语弹文本: {transcription}")
        print(f"📌 建议提问: '{best_match[1]}'")
        print(f"📌 匹配策略: {best_match[0]}")
        print(f"📌 相似度: {best_similarity:.4f}")

        if best_similarity >= settings.AUDIO_REPLY_THRESHOLD:
            print(f"\n✅ 此提问词一定能匹配到该语弹！")
        else:
            print(f"\n⚠️ 相似度仍低于阈值 {settings.AUDIO_REPLY_THRESHOLD}")
            print(f"   建议进一步降低阈值或检查向量服务")

    # 额外测试: 完全相同的文本
    print(f"\n{'='*70}")
    print("极端测试: 提问与语弹完全相同")
    print(f"{'='*70}")
    exact_similarity = await test_similarity(transcription, transcription)
    print(f"相同文本相似度: {exact_similarity:.4f}")

    if exact_similarity < 0.99:
        print("⚠️ 警告: 相同文本相似度不足1.0，向量服务可能有问题！")
    else:
        print("✅ 向量服务正常，相同文本相似度接近1.0")


if __name__ == "__main__":
    asyncio.run(main())
