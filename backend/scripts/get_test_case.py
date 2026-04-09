#!/usr/bin/env python3
"""
从数据库获取语弹并设计测试用例
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


async_session_maker = None

async def get_random_segment():
    """从数据库中获取随机语弹"""
    global async_session_maker
    from shared.database.session import init_db, engine
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    from sqlalchemy import select, func
    from shared.models.audio import AudioSegment

    await init_db()

    # 确保session maker已创建
    if async_session_maker is None:
        async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as db:
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

    transcription = segment.transcription

    print(f"\n{'='*70}")
    print(f"选中语弹:")
    print(f"{'='*70}")
    print(f"ID: {segment.id}")
    print(f"文本: {transcription}")
    print(f"时长: {segment.duration:.2f}秒")
    print(f"来源: {segment.source_title}")

    # 测试完全相同的内容
    print(f"\n{'='*70}")
    print("测试1: 使用完全相同的文本作为提问")
    print(f"{'='*70}")
    exact_similarity = await test_similarity(transcription, transcription)
    print(f"提问: '{transcription}'")
    print(f"语弹: '{transcription}'")
    print(f"相似度: {exact_similarity:.4f}")

    if exact_similarity >= settings.AUDIO_REPLY_THRESHOLD:
        print(f"\n✅ 完全相同的文本相似度 {exact_similarity:.4f} >= {settings.AUDIO_REPLY_THRESHOLD}")
        print(f"✅ 这个提问一定能匹配到该语弹！")
    else:
        print(f"\n❌ 警告: 相同文本相似度 {exact_similarity:.4f} < {settings.AUDIO_REPLY_THRESHOLD}")
        print(f"❌ 向量服务可能有问题！")

    # 测试部分匹配
    print(f"\n{'='*70}")
    print("测试2: 使用语弹中的部分文本作为提问")
    print(f"{'='*70}")

    # 提取关键词
    import re
    # 提取2-4个字符的词组
    test_queries = []

    # 策略1: 完整语弹
    if len(transcription) <= 30:
        test_queries.append(("完整语弹", transcription))

    # 策略2: 前10个字符
    if len(transcription) > 5:
        test_queries.append(("前半部分", transcription[:min(10, len(transcription))]))

    # 策略3: 任意连续4个字符
    for i in range(0, len(transcription) - 3, 4):
        phrase = transcription[i:i+4]
        if len(phrase) >= 4:
            test_queries.append((f"子串{i//4+1}", phrase))

    # 测试
    best_match = None
    best_similarity = 0.0

    for strategy, query in test_queries[:10]:
        similarity = await test_similarity(query, transcription)
        status = "✅" if similarity >= settings.AUDIO_REPLY_THRESHOLD else "❌"
        print(f"\n{status} [{strategy}] 提问: '{query}'")
        print(f"   相似度: {similarity:.4f}")

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (strategy, query)

    # 输出推荐
    print(f"\n{'='*70}")
    print("推荐测试用例")
    print(f"{'='*70}")
    print(f"\n📌 语弹文本: {transcription}")
    print(f"📌 建议提问: '{transcription}' (使用完整文本)")
    print(f"📌 预期相似度: {exact_similarity:.4f}")

    if best_match and best_match[1] != transcription:
        print(f"\n备选提问: '{best_match[1]}'")
        print(f"备选相似度: {best_similarity:.4f}")

    print(f"\n{'='*70}")
    print("测试指令")
    print(f"{'='*70}")
    print(f"\n请在AI对话实验室输入以下内容进行测试:")
    print(f"\n  {transcription}")
    print(f"\n预期结果: 应该返回该语弹的音频")


if __name__ == "__main__":
    asyncio.run(main())
