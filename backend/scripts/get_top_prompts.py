#!/usr/bin/env python3
"""
获取最有可能匹配的测试提问
从audio_segments表中随机取出5条已成功生成向量且字符数超过10个字的真实转录文本，
并为每条文本设计一个最容易触发匹配的用户提问。
"""
import asyncio
import sys
import random
from pathlib import Path
from typing import List, Tuple

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 在导入设置之前设置数据库URL
import os
if os.environ.get("DATABASE_URL") and "@mysql:" in os.environ["DATABASE_URL"]:
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"].replace("@mysql:", "@localhost:")
elif not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
import shared.database.session as db_session
from shared.models.audio import AudioSegment
from shared.models.user import User  # 导入User模型以解决关系
from shared.models.chat import ChatMessage  # 可能也需要
from shared.database.session import init_db
from config import settings

# 确保使用正确的数据库URL
settings.DATABASE_URL = os.environ.get("DATABASE_URL", "mysql+asyncmy://soundverse:password@localhost:3306/soundverse")


def contains_chinese(text: str) -> bool:
    """检查文本是否包含中文字符"""
    import re
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def count_chinese_chars(text: str) -> int:
    """统计中文字符数量"""
    import re
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
    return len(chinese_chars)


def extract_keywords(transcription: str) -> List[str]:
    """
    从转录文本中提取关键词
    这里使用简单的启发式方法，实际应用中可以使用更复杂的NLP技术
    """
    # 移除标点符号
    import re
    cleaned = re.sub(r'[，。：；！？、（）《》【】「」"\'.,!?;:()\[\]{}]', ' ', transcription)

    # 分词（简单空格分词，中文需要更复杂的分词器）
    words = cleaned.split()

    # 过滤停用词和短词
    stop_words = {"现在", "是", "的", "有", "和", "在", "了", "我", "你", "他", "她", "它", "这", "那", "就", "都", "也", "还", "不", "很", "到", "说", "要", "会", "可以", "可能", "应该", "吗", "呢", "吧", "啊", "哦", "嗯", "哈"}

    keywords = []
    for word in words:
        word = word.strip()
        if len(word) >= 2 and word not in stop_words:
            # 如果是中文字符，检查字符数
            if contains_chinese(word):
                if len(word) >= 2:  # 至少2个汉字
                    keywords.append(word)
            else:
                keywords.append(word)

    # 返回前3个关键词
    return keywords[:3]


def generate_test_prompt(transcription: str, keywords: List[str]) -> str:
    """
    为转录文本生成测试提问
    设计原则：
    1. 包含核心关键词
    2. 使用自然的口语表达
    3. 模拟真实用户提问方式
    """
    # 根据内容类型生成不同的提问模板
    transcription_lower = transcription.lower()

    # 判断内容类型
    if any(word in transcription for word in ["天气预报", "气温", "天气", "温度", "多云", "晴天"]):
        # 天气相关
        templates = [
            "{0}的{1}怎么样？",
            "我想了解{0}的{1}",
            "{0}的{1}情况如何？"
        ]
    elif any(word in transcription for word in ["新闻", "广播", "报道", "消息", "事件"]):
        # 新闻相关
        templates = [
            "有什么{0}相关的{1}吗？",
            "我想听听{0}的{1}",
            "{0}有什么{1}？"
        ]
    elif any(word in transcription for word in ["体育", "比赛", "运动员", "球队", "胜利"]):
        # 体育相关
        templates = [
            "{0}的{1}结果如何？",
            "我想了解{0}的{1}",
            "{0}的{1}怎么样了？"
        ]
    elif any(word in transcription for word in ["时间", "点", "钟", "现在", "整"]):
        # 时间相关
        templates = [
            "{0}是什么{1}？",
            "我想知道{0}",
            "{0}的情况"
        ]
    else:
        # 通用模板
        templates = [
            "关于{0}的{1}",
            "我想了解{0}的{1}",
            "{0}的{1}是什么？",
            "有什么{0}相关的{1}吗？"
        ]

    # 确保至少有两个关键词
    if len(keywords) < 2:
        # 如果只有一个关键词，重复使用或使用通用表达
        if keywords:
            templates = [
                "关于{0}的内容",
                "我想了解{0}",
                "{0}是什么？"
            ]
        else:
            # 如果没有提取到关键词，使用转录文本的前几个词
            words = transcription.split()
            if len(words) >= 2:
                templates = ["关于{0}的{1}"]
            else:
                templates = ["关于{0}的内容"]

    # 选择模板并填充关键词
    template = random.choice(templates)

    # 替换模板中的占位符
    try:
        if "{0}" in template and "{1}" in template:
            if len(keywords) >= 2:
                return template.format(keywords[0], keywords[1])
            elif keywords:
                return template.format(keywords[0], "相关信息")
            else:
                # 没有关键词，使用转录文本的前两个词
                words = transcription.split()
                if len(words) >= 2:
                    return template.format(words[0], words[1])
                elif words:
                    return template.format(words[0], "相关内容")
        elif "{0}" in template:
            if keywords:
                return template.format(keywords[0])
            else:
                words = transcription.split()
                if words:
                    return template.format(words[0])
    except (IndexError, KeyError):
        pass

    # 如果所有else都失败，返回默认提问
    if keywords:
        return f"关于{keywords[0]}的内容"
    else:
        return f"关于{transcription[:20]}的内容"


async def get_random_segments_with_vectors() -> List[AudioSegment]:
    """
    随机获取5条已生成向量且字符数超过10个字的真实转录文本
    """
    async with db_session.async_session_maker() as db:
        # 构建查询条件
        stmt = select(AudioSegment).where(
            AudioSegment.vector.is_not(None),  # 已生成向量
            AudioSegment.review_status == "approved",  # 已审核通过
            AudioSegment.transcription.is_not(None),  # 转录文本不为空
            AudioSegment.transcription != "",  # 转录文本非空
            # 排除模拟文本
            ~AudioSegment.transcription.like("这是语音识别的示例文本%"),
            ~AudioSegment.transcription.like("音频片段 %")
        ).order_by(func.rand()).limit(10)  # 获取10条，然后过滤字符数

        result = await db.execute(stmt)
        segments = result.scalars().all()

        # 过滤字符数超过10个字的片段（中文字符）
        filtered_segments = []
        for segment in segments:
            if segment.transcription:
                chinese_char_count = count_chinese_chars(segment.transcription)
                if chinese_char_count >= 10:  # 至少10个汉字
                    filtered_segments.append(segment)
                    if len(filtered_segments) >= 5:
                        break

        return filtered_segments


async def main():
    # 设置编码以避免中文显示问题
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=== 获取最有可能匹配的测试提问 ===")
    print("正在从audio_segments表中随机获取5条已生成向量且字符数超过10个字的真实转录文本...")

    # 在初始化数据库之前，设置数据库URL为localhost（如果当前是mysql主机名）
    import os
    if os.environ.get("DATABASE_URL"):
        current_url = os.environ["DATABASE_URL"]
        # 检查是否是Docker内部的mysql主机名
        if "@mysql:" in current_url:
            # 将@mysql:替换为@localhost:
            new_url = current_url.replace("@mysql:", "@localhost:")
            os.environ["DATABASE_URL"] = new_url
            print(f"已修改DATABASE_URL为: {new_url[:60]}...")
        else:
            print(f"使用现有的DATABASE_URL: {current_url[:60]}...")
    else:
        # 设置默认的本地数据库URL
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"
        print(f"设置DATABASE_URL为: {os.environ['DATABASE_URL']}")

    # 初始化数据库
    await init_db()

    # 获取随机片段
    segments = await get_random_segments_with_vectors()

    if not segments:
        print("错误: 没有找到符合条件的音频片段")
        print("请确保:")
        print("  1. 数据库中有已审核通过的音频片段 (review_status='approved')")
        print("  2. 音频片段已生成向量 (vector字段不为空)")
        print("  3. 转录文本长度超过10个字")
        print("  4. 转录文本为真实内容（非模拟文本）")
        return 1

    print(f"\n找到 {len(segments)} 个符合条件的音频片段:")

    results: List[Tuple[str, str, List[str]]] = []  # (transcription, prompt, keywords)

    for i, segment in enumerate(segments, 1):
        transcription = segment.transcription
        print(f"\n{i}. 广播原声内容: {transcription}")

        # 提取关键词
        keywords = extract_keywords(transcription)
        print(f"   提取的关键词: {keywords}")

        # 生成测试提问
        prompt = generate_test_prompt(transcription, keywords)
        print(f"   测试提问: {prompt}")

        results.append((transcription, prompt, keywords))

    print("\n" + "="*80)
    print("测试提问列表 (复制到小程序中测试):")
    print("="*80)

    for i, (transcription, prompt, keywords) in enumerate(results, 1):
        print(f"\n{i}. [测试提问]: {prompt}")
        print(f"   [广播原声内容]: {transcription}")
        print(f"   [核心关键词]: {', '.join(keywords)}")

    print("\n" + "="*80)
    print("使用说明:")
    print("1. 将上述[测试提问]复制到微信小程序聊天框中发送")
    print("2. 每个提问都应该触发向量检索系统，匹配到对应的[广播原声内容]")
    print("3. 如果匹配失败（返回相似度<0.7或不相关的内容），请检查:")
    print("   - 向量检索维度是否与模型匹配")
    print("   - DashVector集合的维度设置")
    print("   - 嵌入模型(text-embedding-v4)的向量维度")
    print("   - 音频片段的向量是否正确生成和存储")

    # 统计信息
    total_chars = sum(count_chinese_chars(t[0]) for t in results)
    avg_chars = total_chars / len(results) if results else 0
    print(f"\n统计信息: 平均每个片段 {avg_chars:.1f} 个汉字")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))