"""
对话式提示词生成服务
从音频内容生成自然的口语化聊天语句，形成上下文对话
"""
import re
import random
import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.audio import AudioSegment
from services.prompt_generation_service import extract_keywords
from services.natural_conversational_phrases import get_natural_phrases, get_random_phrases

logger = logging.getLogger(__name__)


def extract_natural_phrases(transcription: str) -> List[str]:
    """
    从转录文本中提取自然的短语或短句
    寻找可以作为聊天话题的短句
    """
    if not transcription:
        return []

    # 按句子分割（中文标点，包括省略号）
    sentences = re.split(r'[。！？；;!?.…]', transcription)

    natural_phrases = []

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 3:
            continue

        # 过滤掉太长或太短的句子
        if 3 <= len(sentence) <= 60:
            # 检查是否是自然的口语化句子
            if is_conversational_sentence(sentence):
                natural_phrases.append(sentence)
        elif 60 < len(sentence) <= 150:
            # 对于较长的句子，尝试提取其中的自然短语
            sub_phrases = extract_conversational_subphrases(sentence)
            natural_phrases.extend(sub_phrases)

    # 去重
    unique_phrases = []
    for phrase in natural_phrases:
        if phrase not in unique_phrases:
            unique_phrases.append(phrase)

    return unique_phrases[:8]  # 返回最多8个短语

def is_conversational_sentence(sentence: str) -> bool:
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
    if len(sentence) <= 35 and "，" not in sentence:
        return True

    return False

def extract_conversational_subphrases(long_sentence: str) -> List[str]:
    """
    从长句中提取可能的自然短语
    """
    # 按逗号分割
    parts = re.split(r'[，,、]', long_sentence)

    phrases = []
    for part in parts:
        part = part.strip()
        if 3 <= len(part) <= 40:
            if is_conversational_sentence(part):
                phrases.append(part)

    return phrases


def generate_conversational_statement(keywords: List[str], phrase: Optional[str] = None) -> str:
    """
    生成自然的对话语句（不一定是提问）

    Args:
        keywords: 关键词列表
        phrase: 可选的自然短语

    Returns:
        自然的对话语句
    """
    # 30%的概率直接使用自然短语库中的语句（更口语化）
    if random.random() < 0.3:
        natural_phrases = get_random_phrases(10)
        if natural_phrases:
            return random.choice(natural_phrases)

    if not keywords:
        # 没有关键词时，使用自然短语库或默认语句
        default_statements = get_random_phrases(5)
        if default_statements:
            return random.choice(default_statements)
        # 备用默认语句
        return random.choice([
            "今天有什么新鲜事吗？",
            "最近忙什么呢？",
            "有什么有趣的话题聊聊？",
            "来聊聊天吧",
            "分享点有意思的事情",
        ])

    # 选择主要关键词
    main_keyword = random.choice(keywords) if keywords else ""

    # 更口语化的模板，减少提问比例
    statement_templates = {
        # 陈述句模板 (40%)
        "statement": [
            f"说到{main_keyword}，我想起来一件事",
            f"关于{main_keyword}的话题挺有意思的",
            f"{main_keyword}这个内容我最近也在关注",
            f"我觉得{main_keyword}挺重要的",
            f"{main_keyword}这方面有很多可以聊的",
            f"其实{main_keyword}这个事挺有说头的",
            f"说到{main_keyword}，我有点想法",
            f"{main_keyword}这个我挺感兴趣的",
        ],
        # 感叹句模板 (20%)
        "exclamation": [
            f"{main_keyword}真是太有意思了！",
            f"哇，{main_keyword}这个话题不错！",
            f"说到{main_keyword}，我有同感",
            f"{main_keyword}确实值得关注",
            f"{main_keyword}这个话题我挺感兴趣的",
            f"哎，{main_keyword}这个不错啊",
            f"说到{main_keyword}，我觉得挺好的",
        ],
        # 评论句模板 (20%，减少提问)
        "comment": [
            f"我对{main_keyword}有些看法",
            f"关于{main_keyword}，我有个观点",
            f"{main_keyword}这个内容值得讨论",
            f"对于{main_keyword}，我有些想法",
            f"{main_keyword}这方面我有点经验",
            f"说到{main_keyword}，我的感受是",
        ],
        # 自然疑问句模板 (10%，减少提问比例)
        "natural_question": [
            f"你对{main_keyword}有什么了解吗？",
            f"{main_keyword}这个话题熟悉吗？",
            f"关于{main_keyword}有什么想聊的？",
            f"{main_keyword}方面有什么经验分享？",
        ],
        # 分享句模板 (10%)
        "sharing": [
            f"我最近听说一些关于{main_keyword}的消息",
            f"{main_keyword}这方面我有些了解",
            f"关于{main_keyword}，我知道一些信息",
            f"{main_keyword}这个话题可以分享一下",
            f"我对{main_keyword}有些了解",
        ],
    }

    # 如果有自然短语，可以结合使用 (增加多样性)
    if phrase and len(phrase) <= 30:
        # 基于短语生成更具体的语句
        phrase_based_templates = [
            f"刚才提到的'{phrase}'，挺有意思的",
            f"关于'{phrase}'，可以多聊聊",
            f"'{phrase}'这个话题不错",
            f"说到'{phrase}'，我有些想法",
            f"'{phrase}'这个内容值得关注",
            f"哎，'{phrase}'这个说得对",
            f"说到'{phrase}'，我也有同感",
        ]
        statement_templates["statement"].extend(phrase_based_templates)

    # 加权随机选择类型 (减少提问概率)
    template_weights = {
        "statement": 0.4,      # 40%
        "exclamation": 0.2,    # 20%
        "comment": 0.2,        # 20%
        "natural_question": 0.1, # 10%
        "sharing": 0.1,        # 10%
    }

    template_types = list(template_weights.keys())
    weights = list(template_weights.values())
    template_type = random.choices(template_types, weights=weights, k=1)[0]

    templates = statement_templates[template_type]

    return random.choice(templates)


def generate_contextual_conversation_prompts(
    transcription: str,
    count: int = 5
) -> List[str]:
    """
    从转录文本生成上下文对话提示词

    Args:
        transcription: 音频转录文本
        count: 需要生成的提示词数量

    Returns:
        自然的对话提示词列表
    """
    if not transcription:
        return []

    # 提取关键词
    keywords = extract_keywords(transcription)

    # 提取自然短语
    natural_phrases = extract_natural_phrases(transcription)

    prompts = []

    for i in range(count * 2):  # 生成多一些，然后去重
        # 随机选择使用关键词还是自然短语
        use_phrase = natural_phrases and random.random() < 0.3

        if use_phrase and natural_phrases:
            phrase = random.choice(natural_phrases)
            prompt = generate_conversational_statement(keywords, phrase)
        else:
            prompt = generate_conversational_statement(keywords)

        # 去重
        if prompt not in prompts:
            prompts.append(prompt)

        # 如果已经生成足够数量的提示词，则退出
        if len(prompts) >= count:
            break

    # 如果生成的提示词不足，使用默认提示词补充
    if len(prompts) < count:
        default_prompts = [
            "有什么新鲜事聊聊吗？",
            "今天过得怎么样？",
            "分享点有意思的事情吧",
            "来聊聊天放松一下",
            "有什么话题想讨论吗？",
        ]
        for dp in default_prompts:
            if dp not in prompts:
                prompts.append(dp)
            if len(prompts) >= count:
                break

    return prompts[:count]


async def get_diverse_audio_segments(
    db: AsyncSession,
    limit: int = 50
) -> List[AudioSegment]:
    """
    获取多样化的音频片段（不同来源、不同时间）

    Args:
        db: 数据库会话
        limit: 最大数量

    Returns:
        音频片段列表
    """
    try:
        # 查询已审核通过的音频片段，按创建时间降序，获取最新的
        stmt = (
            select(AudioSegment)
            .where(AudioSegment.review_status == "approved")
            .where(AudioSegment.transcription.isnot(None))
            .order_by(AudioSegment.created_at.desc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        segments = result.scalars().all()

        logger.info(f"获取到 {len(segments)} 个音频片段用于生成对话提示")
        return segments

    except Exception as e:
        logger.error(f"获取音频片段失败: {str(e)}")
        return []


async def generate_conversational_suggestions_from_audio(
    db: AsyncSession,
    suggestion_count: int = 20
) -> List[str]:
    """
    从音频内容生成对话式建议

    Args:
        db: 数据库会话
        suggestion_count: 需要生成的建议数量

    Returns:
        自然的对话建议列表
    """
    try:
        # 获取音频片段
        segments = await get_diverse_audio_segments(db, limit=50)

        if not segments:
            logger.warning("没有找到音频片段，返回默认建议")
            return get_default_conversational_suggestions()

        all_suggestions = []

        # 为每个音频片段生成建议
        for segment in segments:
            if segment.transcription:
                prompts = generate_contextual_conversation_prompts(
                    segment.transcription,
                    count=2  # 每个片段生成2个建议
                )
                all_suggestions.extend(prompts)

                # 如果已经收集足够建议，提前退出
                if len(all_suggestions) >= suggestion_count * 2:
                    break

        # 去重
        unique_suggestions = []
        for suggestion in all_suggestions:
            if suggestion not in unique_suggestions:
                unique_suggestions.append(suggestion)

        # 随机打乱
        random.shuffle(unique_suggestions)

        # 返回指定数量的建议
        return unique_suggestions[:suggestion_count]

    except Exception as e:
        logger.error(f"生成对话式建议失败: {str(e)}")
        return get_default_conversational_suggestions()


def get_default_conversational_suggestions() -> List[str]:
    """
    返回默认的对话式建议列表（自然的聊天语句）
    结合自然短语库和精选的口语化语句
    """
    # 从自然短语库获取短语
    natural_phrases = get_natural_phrases()

    # 精选的口语化语句（补充）
    additional_phrases = [
        # 更口语化的表达
        "哎，今天天气不错啊",
        "说实话，我最近有点忙",
        "其实吧，我觉得这样挺好",
        "你知道吗，我有个发现",
        "说真的，这个挺有意思",

        # 广播节目风格
        "欢迎收听今天的节目",
        "接下来我们聊点轻松的",
        "广告之后马上回来",
        "感谢大家的收听",
        "下期节目再见",

        # 互动性强的语句
        "大家有什么想说的？",
        "说说你的看法呗",
        "一起来聊聊这个话题",
        "分享你的经验吧",
        "你觉得怎么样呢？",

        # 生活化表达
        "今天吃啥了？",
        "周末打算干嘛？",
        "最近看什么剧呢？",
        "有啥好书推荐吗？",
        "锻炼身体了吗？",

        # 情感表达
        "我挺开心的今天",
        "有点小郁闷",
        "感觉还不错",
        "心情挺好的",
        "有点累但充实",
    ]

    # 合并并去重
    all_phrases = list(set(natural_phrases + additional_phrases))

    # 随机打乱顺序
    random.shuffle(all_phrases)

    return all_phrases[:80]  # 返回前80条，足够丰富


async def enrich_chat_suggestions_with_audio_context(
    db: AsyncSession,
    existing_suggestions: List[str],
    enrich_count: int = 10
) -> List[str]:
    """
    用音频内容丰富现有的聊天建议

    Args:
        db: 数据库会话
        existing_suggestions: 现有建议列表
        enrich_count: 需要丰富的数量

    Returns:
        丰富后的建议列表
    """
    try:
        # 从音频生成新的建议
        audio_suggestions = await generate_conversational_suggestions_from_audio(
            db,
            suggestion_count=enrich_count
        )

        # 合并现有建议和音频建议
        all_suggestions = list(set(existing_suggestions + audio_suggestions))

        # 随机打乱
        random.shuffle(all_suggestions)

        return all_suggestions

    except Exception as e:
        logger.error(f"丰富聊天建议失败: {str(e)}")
        return existing_suggestions