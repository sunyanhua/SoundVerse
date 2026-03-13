#!/usr/bin/env python3
"""
从《一路畅通》和《行走天下》中挑选测试提问并验证向量检索效果
任务：
1. 从《一路畅通》（关于怂和爱玩的内容）和《行走天下》（关于奶茶、霸王茶姬、机器人内容）中，各挑选3条文本长度适中（15-30字）的片段。
2. 模仿听众，为这6条片段分别设计一个语义关联最强的提问。
3. 调用搜索接口，预先测试这6个提问的真实相似度分数。
目标：看到0.85以上的匹配分数。
"""
import asyncio
import sys
import random
from pathlib import Path
from typing import List, Tuple, Optional

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 在导入设置之前设置数据库URL
import os
# 使用容器内的环境变量，不修改已有的DATABASE_URL
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy import select, func, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import shared.database.session as db_session
from shared.models.audio import AudioSegment, AudioSource
from shared.models.user import User
from shared.models.chat import ChatMessage
from shared.database.session import init_db
from config import settings
from services.search_service import search_audio_segments_by_text

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


def generate_semantic_prompt(transcription: str, keywords: List[str]) -> str:
    """
    为转录文本生成语义关联最强的提问
    设计原则：
    1. 包含核心关键词
    2. 使用自然的口语表达
    3. 模拟真实用户提问方式
    4. 针对特定内容类型优化
    """
    # 根据内容类型生成不同的提问模板
    transcription_lower = transcription.lower()

    # 判断内容类型
    if any(word in transcription for word in ["怂", "爱玩", "游戏", "娱乐"]):
        # 《一路畅通》相关内容
        templates = [
            "关于{0}的{1}有什么说法？",
            "我想了解{0}和{1}的关系",
            "{0}是怎么影响{1}的？"
        ]
    elif any(word in transcription for word in ["奶茶", "霸王茶姬", "机器人", "人工智能", "科技"]):
        # 《行走天下》相关内容
        templates = [
            "{0}和{1}有什么关联？",
            "关于{0}的{1}技术有什么进展？",
            "{0}对{1}有什么影响？"
        ]
    elif any(word in transcription for word in ["天气预报", "气温", "天气", "温度", "多云", "晴天"]):
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


async def get_segments_from_source(source_title_pattern: str, limit: int = 3) -> List[AudioSegment]:
    """
    从指定标题的音频源中获取符合条件的片段
    条件：
    1. 文本长度15-30字（中文字符）
    2. 已审核通过
    3. 已生成向量
    """
    async with db_session.async_session_maker() as db:
        # 首先查找匹配的音频源
        source_stmt = select(AudioSource).where(
            AudioSource.title.like(f"%{source_title_pattern}%")
        )
        source_result = await db.execute(source_stmt)
        sources = source_result.scalars().all()

        if not sources:
            print(f"警告: 未找到标题包含 '{source_title_pattern}' 的音频源")
            return []

        source_ids = [source.id for source in sources]

        # 查询符合条件的音频片段
        stmt = select(AudioSegment).options(
            selectinload(AudioSegment.source)
        ).where(
            AudioSegment.source_id.in_(source_ids),
            AudioSegment.vector.is_not(None),  # 已生成向量
            AudioSegment.review_status == "approved",  # 已审核通过
            AudioSegment.transcription.is_not(None),  # 转录文本不为空
            AudioSegment.transcription != "",  # 转录文本非空
            # 排除模拟文本
            ~AudioSegment.transcription.like("这是语音识别的示例文本%"),
            ~AudioSegment.transcription.like("音频片段 %")
        ).order_by(func.rand())

        result = await db.execute(stmt)
        segments = result.scalars().all()

        # 过滤字符数在15-30字之间的片段
        filtered_segments = []
        for segment in segments:
            if segment.transcription:
                chinese_char_count = count_chinese_chars(segment.transcription)
                if 15 <= chinese_char_count <= 30:  # 15-30个汉字
                    filtered_segments.append(segment)
                    if len(filtered_segments) >= limit:
                        break

        return filtered_segments


async def test_search_score(prompt: str, target_segment_id: str) -> Optional[float]:
    """
    测试搜索提问的相似度分数
    返回目标片段的相似度分数，如果未找到返回None
    """
    try:
        # 搜索相似片段
        search_results = await search_audio_segments_by_text(
            prompt,
            top_k=10,  # 扩大搜索范围
            similarity_threshold=0.0  # 不设阈值，获取所有结果
        )

        # 查找目标片段的分数
        for segment_id, similarity in search_results:
            if segment_id == target_segment_id:
                return similarity

        return None
    except Exception as e:
        print(f"搜索测试失败: {str(e)}")
        return None


async def main():
    # 设置编码以避免中文显示问题
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=== 测试2370条数据的检索威力 ===")
    print("任务: 从《一路畅通》和《行走天下》中各挑选3条片段，生成提问并测试相似度分数")
    print("目标: 期望相似度分数 > 0.85\n")

    # 使用现有的DATABASE_URL（容器内已经配置好）
    import os
    current_url = os.environ.get("DATABASE_URL")
    if current_url:
        print(f"使用DATABASE_URL: {current_url[:60]}...")
    else:
        print("警告: DATABASE_URL环境变量未设置")
        return 1

    # 初始化数据库
    await init_db()

    # 初始化搜索服务（可能需要）
    from services.search_service import search_service
    await search_service.initialize()

    # 获取《一路畅通》的片段
    print("\n1. 获取《一路畅通》片段...")
    yilutong_segments = await get_segments_from_source("一路畅通", limit=3)
    if not yilutong_segments:
        print("  未找到符合条件的《一路畅通》片段")
        # 尝试更宽松的条件
        print("  尝试放宽条件...")
        yilutong_segments = await get_segments_from_source("一路畅通", limit=10)

    # 获取《行走天下》的片段
    print("2. 获取《行走天下》片段...")
    xingzoutianxia_segments = await get_segments_from_source("行走天下", limit=3)
    if not xingzoutianxia_segments:
        print("  未找到符合条件的《行走天下》片段")
        # 尝试更宽松的条件
        print("  尝试放宽条件...")
        xingzoutianxia_segments = await get_segments_from_source("行走天下", limit=10)

    all_segments = yilutong_segments + xingzoutianxia_segments

    if not all_segments:
        print("错误: 没有找到任何符合条件的音频片段")
        print("请确保:")
        print("  1. 数据库中有《一路畅通》和《行走天下》的音频源")
        print("  2. 音频片段已审核通过 (review_status='approved')")
        print("  3. 音频片段已生成向量 (vector字段不为空)")
        print("  4. 转录文本长度在15-30字之间")
        return 1

    print(f"\n找到 {len(all_segments)} 个符合条件的音频片段:")
    for i, segment in enumerate(all_segments, 1):
        source_title = segment.source.title if segment.source else "未知"
        chinese_chars = count_chinese_chars(segment.transcription) if segment.transcription else 0
        print(f"  {i}. [{source_title}] ID:{segment.id} {segment.transcription[:60]}... (字数: {chinese_chars})")

    # 只打印片段信息后退出
    import sys
    sys.exit(0)

    print("\n" + "="*80)
    print("生成测试提问并验证相似度:")
    print("="*80)

    results = []

    for i, segment in enumerate(all_segments, 1):
        transcription = segment.transcription
        source_title = segment.source.title if segment.source else "未知"

        print(f"\n{i}. 广播原声内容: {transcription}")
        print(f"   来源: {source_title}")

        # 提取关键词
        keywords = extract_keywords(transcription)
        print(f"   提取的关键词: {keywords}")

        # 生成测试提问
        prompt = generate_semantic_prompt(transcription, keywords)
        print(f"   测试提问: {prompt}")

        # 测试搜索分数
        print(f"   正在测试搜索相似度...")
        similarity = await test_search_score(prompt, segment.id)

        if similarity is not None:
            score_color = "\033[92m" if similarity >= 0.85 else "\033[91m"  # 绿色/红色
            print(f"   相似度分数: {score_color}{similarity:.4f}\033[0m")
            if similarity >= 0.85:
                print("   ✅ 达到目标分数 (>0.85)")
            else:
                print("   ❌ 未达到目标分数")
        else:
            print(f"   警告: 未找到目标片段的搜索结果")
            similarity = 0.0

        results.append({
            "segment_id": segment.id,
            "source_title": source_title,
            "transcription": transcription,
            "prompt": prompt,
            "similarity": similarity,
            "keywords": keywords
        })

    print("\n" + "="*80)
    print("测试结果汇总:")
    print("="*80)

    total_above_threshold = sum(1 for r in results if r["similarity"] >= 0.85)
    print(f"达到目标分数(>0.85)的提问: {total_above_threshold}/{len(results)}")

    for i, result in enumerate(results, 1):
        source_title = result["source_title"]
        prompt = result["prompt"]
        similarity = result["similarity"]
        transcription_preview = result["transcription"][:50] + "..." if len(result["transcription"]) > 50 else result["transcription"]

        score_marker = "✅" if similarity >= 0.85 else "❌"
        print(f"\n{i}. {score_marker} [{source_title}]")
        print(f"   提问: {prompt}")
        print(f"   相似度: {similarity:.4f}")
        print(f"   广播原声: {transcription_preview}")

    print("\n" + "="*80)
    print("小程序测试建议:")
    print("="*80)

    for i, result in enumerate(results, 1):
        prompt = result["prompt"]
        source_title = result["source_title"]
        similarity = result["similarity"]

        if similarity >= 0.85:
            print(f"{i}. 在小程序中发送: \"{prompt}\"")
            print(f"   预期匹配: {source_title}中的相关片段")
            print(f"   预期相似度: {similarity:.4f}")
        else:
            print(f"{i}. (低分测试) 在小程序中发送: \"{prompt}\"")
            print(f"   当前相似度: {similarity:.4f} (可能需要优化提问)")

    # 统计信息
    if results:
        avg_similarity = sum(r["similarity"] for r in results) / len(results)
        print(f"\n统计信息:")
        print(f"  • 平均相似度: {avg_similarity:.4f}")
        print(f"  • 最高相似度: {max(r['similarity'] for r in results):.4f}")
        print(f"  • 最低相似度: {min(r['similarity'] for r in results):.4f}")
        print(f"  • 达标率: {total_above_threshold}/{len(results)} ({total_above_threshold/len(results)*100:.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))