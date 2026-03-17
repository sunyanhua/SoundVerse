#!/usr/bin/env python3
"""
从音频转录文本中提取自然的口语化短语
用于改进聊天提示词库
"""
import asyncio
import re
import sys
from pathlib import Path
from typing import List

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import os
os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func
from shared.models.audio import AudioSegment

def extract_natural_conversational_phrases(text: str, max_length: int = 200) -> List[str]:
    """
    从文本中提取自然的对话短语
    寻找可以作为聊天话题的短句
    """
    if not text:
        return []

    # 更自然的分句模式（中文标点）
    sentence_delimiters = r'[。！？；;!?.…]'
    sentences = re.split(sentence_delimiters, text)

    natural_phrases = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 4:
            continue

        # 过滤太长或太短的句子
        if 4 <= len(sentence) <= 50:
            # 检查是否是自然的口语化句子
            if is_natural_conversational_sentence(sentence):
                natural_phrases.append(sentence)
        elif 50 < len(sentence) <= max_length:
            # 对于较长的句子，尝试提取其中的自然短语
            sub_phrases = extract_sub_phrases(sentence)
            natural_phrases.extend(sub_phrases)

    # 去重
    unique_phrases = []
    for phrase in natural_phrases:
        if phrase not in unique_phrases:
            unique_phrases.append(phrase)

    return unique_phrases[:20]  # 返回最多20个短语

def is_natural_conversational_sentence(sentence: str) -> bool:
    """
    判断句子是否是自然的口语化句子
    """
    # 常见的口语化开头或结尾
    conversational_patterns = [
        r'^(今天|明天|昨天|现在|刚才|最近|这.+天)',
        r'^(我觉得|我认为|我感觉|我想说|我听说|我记得)',
        r'^(大家|各位|朋友们|同学们)',
        r'^(说到|关于|对于|至于)',
        r'^(其实|实际上|说实话|坦白说)',
        r'^(比如|例如|比如说|举个例子)',
        r'^(首先|其次|然后|最后|接下来)',
        r'^(总之|总而言之|总的来说|简而言之)',
        r'^(另外|此外|还有|再者)',
        r'^(不过|但是|然而|可是)',
        r'^(如果|假如|要是|假设)',
        r'^(因为|由于|所以|因此|于是)',
        r'^(虽然|尽管|即使|就算)',
        r'.*(吧|嘛|呢|啊|呀|哦|啦|么|呗|哩|哟|诶)$',
    ]

    # 检查是否匹配口语化模式
    for pattern in conversational_patterns:
        if re.search(pattern, sentence):
            return True

    # 检查是否包含常见的话题词汇
    topic_words = [
        "说", "讲", "聊", "谈", "介绍", "报道", "新闻", "消息", "表示",
        "认为", "觉得", "经验", "故事", "事情", "话题", "问题", "情况",
        "天气", "时间", "地点", "人物", "事件", "原因", "结果", "方法",
        "建议", "意见", "看法", "观点", "想法", "感受", "体验"
    ]

    for word in topic_words:
        if word in sentence:
            return True

    # 检查句子结构（简单句子更自然）
    if len(sentence) <= 30 and "，" not in sentence:
        return True

    return False

def extract_sub_phrases(long_sentence: str) -> List[str]:
    """
    从长句中提取可能的自然短语
    """
    # 按逗号分割
    parts = re.split(r'[，,、]', long_sentence)

    phrases = []
    for part in parts:
        part = part.strip()
        if 4 <= len(part) <= 30:
            if is_natural_conversational_sentence(part):
                phrases.append(part)

    return phrases

async def extract_phrases_from_database():
    """从数据库中提取自然短语"""
    DATABASE_URL = os.environ.get("DATABASE_URL", "mysql+asyncmy://soundverse:password@localhost:3306/soundverse")
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 查询有转录文本的音频片段（随机选择100个）
        stmt = (
            select(AudioSegment)
            .where(AudioSegment.transcription.isnot(None))
            .where(AudioSegment.review_status == "approved")
            .order_by(func.rand())  # 随机排序
            .limit(100)
        )

        result = await db.execute(stmt)
        segments = result.scalars().all()

        print(f"从 {len(segments)} 个音频片段中提取自然短语...")
        print("=" * 80)

        all_phrases = []

        for i, segment in enumerate(segments, 1):
            if segment.transcription:
                phrases = extract_natural_conversational_phrases(segment.transcription)
                if phrases:
                    all_phrases.extend(phrases)
                    print(f"片段 {i}: 提取到 {len(phrases)} 个短语")
                    for phrase in phrases[:3]:  # 显示前3个
                        print(f"  - {phrase}")
                    print()

            # 每10个片段显示一次进度
            if i % 10 == 0:
                print(f"进度: {i}/{len(segments)}，已提取 {len(all_phrases)} 个短语")
                print("-" * 60)

        # 去重
        unique_phrases = []
        for phrase in all_phrases:
            if phrase not in unique_phrases:
                unique_phrases.append(phrase)

        print("=" * 80)
        print(f"总共提取到 {len(unique_phrases)} 个唯一的自然短语")
        print("\n示例短语:")
        print("-" * 40)

        # 显示一些示例
        for i, phrase in enumerate(unique_phrases[:30], 1):
            print(f"{i:2d}. {phrase}")

        # 保存到文件
        output_file = Path(__file__).parent / "natural_conversational_phrases.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# 自然对话短语库\n")
            f.write(f"# 从 {len(segments)} 个音频片段中提取\n")
            f.write(f"# 提取时间: {asyncio.get_event_loop().time()}\n")
            f.write(f"# 总共 {len(unique_phrases)} 个短语\n\n")

            for i, phrase in enumerate(unique_phrases, 1):
                f.write(f"{i}. {phrase}\n")

        print(f"\n已保存到: {output_file}")

        return unique_phrases

async def main():
    try:
        await extract_phrases_from_database()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)