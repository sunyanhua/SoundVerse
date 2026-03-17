"""
提示词生成服务
根据音频内容动态生成相关提示词
"""

import re
import random
from typing import List, Optional


def extract_keywords(transcription: str) -> List[str]:
    """从转录文本中提取关键词（优化版本）"""
    if not transcription:
        return []

    # 移除标点符号和数字
    cleaned = re.sub(r'[，。：；！？、（）《》【】「」"\'.,!?;:()\[\]{}0-9]', ' ', transcription)

    # 中文分词简单实现：按字符分割，然后组合成2-4个字符的词语
    characters = [ch for ch in cleaned if ch.strip() and ch != ' ']

    stop_words = {"现在", "是", "的", "有", "和", "在", "了", "我", "你", "他", "她", "它", "这", "那", "就", "都", "也", "还", "不", "很", "到", "说", "要", "会", "可以", "可能", "应该", "吗", "呢", "吧", "啊", "哦", "嗯", "哈", "然后", "然后呢", "家长", "说", "哎呀", "一种", "锻炼", "计算"}

    # 扩展停用词：代词、连接词、常见虚词
    extended_stop_words = stop_words.union({
        "这个", "那个", "这些", "那些", "什么", "怎么", "为什么", "如何",
        "因为", "所以", "但是", "而且", "如果", "那么", "然后", "接着",
        "首先", "其次", "最后", "总之", "例如", "比如", "尤其", "特别",
        "一个", "一些", "一种", "一点", "一下", "一起", "一样", "一般",
        "一下", "一定", "一起", "一切", "一样", "一些", "一点", "一种"
    })

    keywords = []

    # 生成2-4个字符的n-gram
    ngrams = []
    for n in range(2, 5):  # 2-4个字符
        for i in range(len(characters) - n + 1):
            ngram = ''.join(characters[i:i+n])
            ngrams.append(ngram)

    # 过滤停用词和无效词语
    for word in ngrams:
        word = word.strip()
        # 只保留长度2-4的中文词语
        if 2 <= len(word) <= 4 and word not in extended_stop_words:
            if any('\u4e00' <= char <= '\u9fff' for char in word):
                # 避免纯英文或符号
                keywords.append(word)

    # 去重并限制数量
    unique_keywords = []
    for kw in keywords:
        if kw not in unique_keywords:
            unique_keywords.append(kw)

    # 如果没有提取到关键词，尝试使用较长的短语
    if not unique_keywords and len(characters) > 0:
        # 组合前3-5个字符作为一个短语
        phrase = ''.join(characters[:min(5, len(characters))])
        if 3 <= len(phrase) <= 8:
            unique_keywords.append(phrase)

    return unique_keywords[:3]  # 返回最多3个关键词


def generate_semantic_prompt(transcription: str, keywords: List[str]) -> str:
    """为转录文本生成语义关联最强的提问（优化版本，更自然）"""
    if not keywords:
        # 没有关键词时，使用转录文本的前几个词
        preview = transcription[:30].strip()
        if preview:
            # 更自然的表达
            templates = [
                f"能介绍一下'{preview}'吗？",
                f"关于'{preview}'的内容是什么？",
                f"我想了解'{preview}'的相关信息",
                f"有什么关于'{preview}'的内容可以分享吗？",
                f"'{preview}'是什么？"
            ]
            return random.choice(templates)
        return "关于这个内容的问题"

    # 根据关键词数量选择不同的模板
    if len(keywords) == 1:
        templates = [
            f"能介绍一下{keywords[0]}吗？",
            f"我想了解{keywords[0]}的相关信息",
            f"{keywords[0]}是什么？",
            f"有什么关于{keywords[0]}的内容吗？",
            f"关于{keywords[0]}的内容是什么？",
            f"{keywords[0]}有什么特点？",
            f"请讲讲{keywords[0]}",
            f"{keywords[0]}的相关知识有哪些？"
        ]
    elif len(keywords) >= 2:
        # 使用两个关键词创建更自然的提问
        templates = [
            f"{keywords[0]}和{keywords[1]}有什么关系？",
            f"能介绍一下{keywords[0]}和{keywords[1]}吗？",
            f"我想了解{keywords[0]}和{keywords[1]}",
            f"{keywords[0]}对{keywords[1]}有什么影响？",
            f"有什么{keywords[0]}相关的{keywords[1]}信息吗？",
            f"关于{keywords[0]}和{keywords[1]}的内容",
            f"{keywords[0]}与{keywords[1]}有什么联系？",
            f"请讲讲{keywords[0]}和{keywords[1]}"
        ]

    return random.choice(templates)


def generate_prompts_for_audio(transcription: str, count: int = 3) -> List[str]:
    """
    为音频转录文本生成多个相关提示词

    Args:
        transcription: 音频转录文本
        count: 需要生成的提示词数量（默认3个）

    Returns:
        提示词列表
    """
    if not transcription:
        return []

    keywords = extract_keywords(transcription)
    prompts = []

    # 生成多个变体
    for i in range(count):
        # 稍微改变关键词顺序或选择不同的模板
        if keywords:
            # 随机选择关键词组合
            if len(keywords) >= 2:
                # 随机选择两个关键词
                selected = random.sample(keywords, min(2, len(keywords)))
                # 随机选择模板
                templates = [
                    f"{selected[0]}和{selected[1]}有什么关系？",
                    f"能介绍一下{selected[0]}和{selected[1]}吗？",
                    f"我想了解{selected[0]}和{selected[1]}",
                    f"{selected[0]}对{selected[1]}有什么影响？",
                    f"有什么{selected[0]}相关的{selected[1]}信息吗？",
                    f"关于{selected[0]}和{selected[1]}的内容",
                    f"{selected[0]}与{selected[1]}有什么联系？",
                    f"请讲讲{selected[0]}和{selected[1]}"
                ]
                prompt = random.choice(templates)
            else:
                # 单个关键词
                templates = [
                    f"能介绍一下{keywords[0]}吗？",
                    f"我想了解{keywords[0]}的相关信息",
                    f"{keywords[0]}是什么？",
                    f"有什么关于{keywords[0]}的内容吗？",
                    f"关于{keywords[0]}的内容是什么？",
                    f"{keywords[0]}有什么特点？",
                    f"请讲讲{keywords[0]}",
                    f"{keywords[0]}的相关知识有哪些？"
                ]
                prompt = random.choice(templates)
        else:
            # 没有关键词时，使用转录文本片段
            preview = transcription[:30].strip()
            if preview:
                prompt = f"关于'{preview}'的内容是什么？"
            else:
                prompt = "关于这个内容的问题"

        # 去重
        if prompt not in prompts:
            prompts.append(prompt)

        # 如果已经生成足够数量的提示词，则退出
        if len(prompts) >= count:
            break

    # 如果生成的提示词不足，使用默认提示词补充
    if len(prompts) < count:
        default_prompts = [
            "现在几点了？",
            "北京时间是多少？",
            "有什么新闻广播吗？",
            "天气预报",
            "体育新闻"
        ]
        for dp in default_prompts:
            if dp not in prompts:
                prompts.append(dp)
            if len(prompts) >= count:
                break

    return prompts[:count]


async def generate_prompts_for_audio_segment(audio_segment) -> List[str]:
    """
    为音频片段生成相关提示词

    Args:
        audio_segment: AudioSegment对象（需包含transcription字段）

    Returns:
        提示词列表
    """
    if not audio_segment or not audio_segment.transcription:
        return []

    return generate_prompts_for_audio(audio_segment.transcription)