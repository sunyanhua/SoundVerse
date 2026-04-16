"""
匹配度服务 - 评估语弹作为回复的合适程度

从"相似度"转向"匹配度"：
- 相似度：文本内容的相似程度（cosine similarity）
- 匹配度：语弹作为回复的合适程度（question-answer relevance）

新增：意图识别驱动的匹配
- 识别用户请求类型（广播/方言/音乐/话题等）
- 根据意图匹配对应类型的语弹
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ai_models.llm_service import LLMService

logger = logging.getLogger(__name__)


class UserIntent(Enum):
    """用户意图类型"""
    REQUEST_BROADCAST = "request_broadcast"  # 请求广播/开场白
    REQUEST_DIALECT = "request_dialect"      # 请求方言/特色语言
    REQUEST_MUSIC = "request_music"          # 请求音乐/歌曲
    REQUEST_TOPIC = "request_topic"          # 请求特定话题
    QUESTION = "question"                    # 提问
    STATEMENT = "statement"                  # 陈述
    GREETING = "greeting"                    # 问候
    UNKNOWN = "unknown"                      # 未知


@dataclass
class RelevanceScore:
    """匹配度评分结果"""
    score: float  # 0-1 的匹配度分数
    reasoning: str  # 评分理由
    is_match: bool  # 是否达到匹配门槛
    user_intent: Optional[UserIntent] = None  # 识别的用户意图
    segment_tags: List[str] = None  # 语弹标签匹配情况


class RelevanceService:
    """
    匹配度评估服务
    使用LLM判断语弹是否适合作为对用户输入的回复
    新增意图识别驱动的智能匹配
    """

    # 意图关键词映射
    INTENT_KEYWORDS = {
        UserIntent.REQUEST_BROADCAST: [
            "广播", "开场", "开场白", "节目开始", "来段节目", "来段广播",
            "听广播", "放广播", "节目开场", "主持人开场"
        ],
        UserIntent.REQUEST_DIALECT: [
            "东北话", "方言", "东北", "那嘎达", "俺们", "土话",
            "地方话", "乡音", "口音", "特色语言"
        ],
        UserIntent.REQUEST_MUSIC: [
            "歌", "歌曲", "音乐", "唱歌", "听歌", "来首歌", "放首歌",
            "唱歌听听", "音乐片段", "听歌", " Sing", "music"
        ],
        UserIntent.REQUEST_TOPIC: [
            "讲讲", "说说", "聊聊", "谈", "讨论", "介绍", "来段",
            "我想听", "给我讲", "说说看"
        ],
        UserIntent.GREETING: [
            "你好", "您好", "嗨", "Hello", "Hi", "早上好", "晚上好"
        ]
    }

    # 语弹内容标签规则
    SEGMENT_TAG_RULES = {
        "broadcast_opening": ["欢迎收听", "我是", "主持人", "开场", "节目开始"],
        "dialect_northeast": ["那嘎达", "俺们", "东北", "嘎达", "咋地"],
        "music_singing": ["歌词", "歌曲", "唱", "music", "旋律"],
        "train_highspeed": ["高铁", "列车", "通勤", "京津", "京沪"],
        "travel_flight": ["飞机", "航班", "飞行", "机场", "航空"],
        "daily_chat": ["聊天", "闲聊", "说话", "谈", "聊"]
    }

    def __init__(self):
        self.llm_service = LLMService()

    def detect_intent(self, user_query: str) -> UserIntent:
        """
        快速意图识别 - 基于关键词匹配
        """
        query_lower = user_query.lower()

        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    return intent

        # 判断是问题还是陈述
        if any(q in query_lower for q in ["?", "？", "吗", "呢", "什么", "怎么", "为什么", "多少", "几"]):
            return UserIntent.QUESTION

        return UserIntent.UNKNOWN

    def detect_segment_tags(self, segment_text: str) -> List[str]:
        """
        识别语弹内容的标签
        """
        if not segment_text:
            return []

        tags = []
        text_lower = segment_text.lower()

        for tag, keywords in self.SEGMENT_TAG_RULES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    tags.append(tag)
                    break

        return tags

    def calculate_intent_match_score(
        self,
        user_intent: UserIntent,
        segment_tags: List[str],
        segment_text: str
    ) -> Tuple[float, str]:
        """
        根据意图和语弹标签计算匹配分数
        """
        # 意图到标签的映射
        intent_tag_mapping = {
            UserIntent.REQUEST_BROADCAST: ["broadcast_opening"],
            UserIntent.REQUEST_DIALECT: ["dialect_northeast"],
            UserIntent.REQUEST_MUSIC: ["music_singing"],
        }

        target_tags = intent_tag_mapping.get(user_intent, [])

        if not target_tags:
            return 0.0, ""

        # 检查是否有标签匹配
        matched_tags = [tag for tag in target_tags if tag in segment_tags]

        if matched_tags:
            # 标签匹配，给予高分
            return 0.85, f"意图'{user_intent.value}'匹配标签: {', '.join(matched_tags)}"

        # 没有标签匹配，但意图明确，降低分数但仍有匹配可能
        return 0.3, f"意图明确但无对应标签语弹"

    async def detect_intent_with_llm(self, user_query: str) -> Tuple[UserIntent, str]:
        """
        使用LLM进行更精确的意图识别
        """
        prompt = f"""分析用户输入的意图类型。

用户输入: "{user_query}"

请判断意图类型（只返回JSON格式）:
{{
    "intent": "request_broadcast|request_dialect|request_music|request_topic|question|greeting|unknown",
    "reasoning": "简要解释为什么是这个意图",
    "expected_content": "期望返回的语弹内容类型"
}}

示例:
用户: "来段广播吧"
返回: {{"intent": "request_broadcast", "reasoning": "用户明确要求听广播开场", "expected_content": "广播开场白、节目介绍"}}

用户: "来段东北话"
返回: {{"intent": "request_dialect", "reasoning": "用户要求听东北方言", "expected_content": "东北话、那嘎达方言片段"}}

用户: "放首歌听听"
返回: {{"intent": "request_music", "reasoning": "用户要求听音乐", "expected_content": "歌曲、音乐片段"}}
"""

        try:
            result = await self.llm_service.generate_chat_response(
                query=prompt,
                system_prompt="你是意图识别专家，只返回JSON格式结果。",
                temperature=0.1,
                max_tokens=150
            )

            response = result.get("reply", "") if result.get("success") else ""

            # 解析JSON
            import json
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                data = json.loads(json_match.group())
                intent_str = data.get("intent", "unknown")
                reasoning = data.get("reasoning", "")

                try:
                    intent = UserIntent(intent_str)
                    return intent, reasoning
                except ValueError:
                    pass

        except Exception as e:
            logger.warning(f"LLM意图识别失败: {e}")

        return UserIntent.UNKNOWN, "LLM识别失败，使用备用方案"

    async def calculate_relevance(
        self,
        user_query: str,
        segment_text: str,
        segment_emotion: Optional[str] = None,
        user_intent: Optional[UserIntent] = None
    ) -> RelevanceScore:
        """
        计算语弹作为回复的匹配度（增强版 - 支持意图驱动匹配）

        Args:
            user_query: 用户输入（问题或陈述）
            segment_text: 语弹的转录文本
            segment_emotion: 语弹的情感标签（可选）
            user_intent: 用户意图（如果已识别）

        Returns:
            RelevanceScore: 匹配度评分结果
        """
        # 步骤1: 识别用户意图（如果未提供）
        if user_intent is None:
            user_intent = self.detect_intent(user_query)

        # 步骤2: 识别语弹标签
        segment_tags = self.detect_segment_tags(segment_text)

        # 步骤3: 意图驱动匹配（如果是请求类意图）
        intent_boost = 0.0
        intent_reasoning = ""

        if user_intent in [
            UserIntent.REQUEST_BROADCAST,
            UserIntent.REQUEST_DIALECT,
            UserIntent.REQUEST_MUSIC
        ]:
            intent_score, intent_reasoning = self.calculate_intent_match_score(
                user_intent, segment_tags, segment_text
            )

            # 如果意图明确且有标签匹配，直接返回高分
            if intent_score >= 0.8:
                return RelevanceScore(
                    score=intent_score,
                    reasoning=f"[意图匹配] {intent_reasoning}",
                    is_match=True,
                    user_intent=user_intent,
                    segment_tags=segment_tags
                )

            # 意图匹配但分数不高，给予一定提升
            intent_boost = intent_score * 0.3

        # 步骤4: 使用LLM评估语义匹配度
        prompt = self._build_relevance_prompt(user_query, segment_text, segment_emotion, user_intent)

        try:
            result = await self.llm_service.generate_chat_response(
                query=prompt,
                system_prompt="你是一个专业的语义匹配评估专家。请根据用户输入和候选语弹，评估语弹作为回复的匹配程度。只返回JSON格式的评分结果。",
                temperature=0.3,
                max_tokens=200
            )

            response = result.get("reply", "") if result.get("success") else ""
            score, reasoning = self._parse_relevance_response(response)

            # 步骤5: 综合评分（语义评分 + 意图增强）
            final_score = min(1.0, score + intent_boost)

            # 组合理由
            if intent_reasoning:
                final_reasoning = f"{intent_reasoning}; {reasoning}"
            else:
                final_reasoning = reasoning

            return RelevanceScore(
                score=final_score,
                reasoning=final_reasoning,
                is_match=final_score >= 0.48,
                user_intent=user_intent,
                segment_tags=segment_tags
            )

        except Exception as e:
            logger.error(f"匹配度计算失败: {e}")
            # 失败时返回低匹配度，但不阻断流程
            return RelevanceScore(
                score=intent_boost,  # 至少返回意图匹配分数
                reasoning=f"评估失败: {str(e)}; {intent_reasoning}",
                is_match=intent_boost >= 0.48,
                user_intent=user_intent,
                segment_tags=segment_tags
            )

    async def batch_calculate_relevance(
        self,
        user_query: str,
        segments: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], RelevanceScore]]:
        """
        批量计算多个语弹的匹配度（增强版 - 支持意图驱动排序）

        Args:
            user_query: 用户输入
            segments: 语弹列表，每个包含 text, emotion 等字段

        Returns:
            按匹配度排序的 (语弹, 匹配度) 列表
        """
        # 首先识别用户意图（只需识别一次）
        user_intent = self.detect_intent(user_query)

        # 如果是意图明确的请求，尝试用LLM进一步确认
        if user_intent in [
            UserIntent.REQUEST_BROADCAST,
            UserIntent.REQUEST_DIALECT,
            UserIntent.REQUEST_MUSIC,
            UserIntent.REQUEST_TOPIC
        ]:
            llm_intent, llm_reasoning = await self.detect_intent_with_llm(user_query)
            if llm_intent != UserIntent.UNKNOWN:
                user_intent = llm_intent
                logger.info(f"LLM意图识别: {user_query} -> {user_intent.value}, 理由: {llm_reasoning}")

        results = []

        for segment in segments:
            score = await self.calculate_relevance(
                user_query=user_query,
                segment_text=segment.get("transcription", ""),
                segment_emotion=segment.get("emotion"),
                user_intent=user_intent
            )
            results.append((segment, score))

        # 按匹配度降序排序
        results.sort(key=lambda x: x[1].score, reverse=True)

        # 记录意图识别结果（用于调试）
        if results:
            logger.info(f"查询 '{user_query[:30]}...' 识别意图: {user_intent.value}, 最佳匹配分数: {results[0][1].score:.2f}")

        return results

    def _build_relevance_prompt(
        self,
        user_query: str,
        segment_text: str,
        segment_emotion: Optional[str] = None,
        user_intent: Optional[UserIntent] = None
    ) -> str:
        """
        构建匹配度评估提示词（增强版 - 考虑用户意图）
        """
        emotion_info = f"\n语弹情感: {segment_emotion}" if segment_emotion else ""
        intent_info = f"\n用户意图: {user_intent.value if user_intent else '未知'}" if user_intent else ""

        # 根据意图调整评分指引
        intent_guidance = ""
        if user_intent == UserIntent.REQUEST_BROADCAST:
            intent_guidance = """
特别指引（用户请求广播/开场）:
- 开场白、节目介绍、主持人自我介绍的语弹应获得高分
- 广播节目开头的欢迎词、介绍语最为匹配"""
        elif user_intent == UserIntent.REQUEST_DIALECT:
            intent_guidance = """
特别指引（用户请求方言内容）:
- 包含方言特色词汇（如"那嘎达"、"俺们"等）的语弹应获得高分
- 东北话、地方特色语言片段最为匹配"""
        elif user_intent == UserIntent.REQUEST_MUSIC:
            intent_guidance = """
特别指引（用户请求音乐/歌曲）:
- 歌词、歌曲片段、音乐内容的语弹应获得高分
- 与音乐相关的对话或歌词引用最为匹配"""

        return f"""请评估以下语弹作为回复的匹配程度。

用户输入: "{user_query}"{intent_info}{emotion_info}

候选语弹: "{segment_text}"

请从以下维度评估匹配度（0-100分）：
1. 语义相关性（40分）: 语弹内容是否与用户输入的话题相关
2. 回复 appropriateness（30分）: 语弹是否适合作为对用户输入的回应（不是重复，而是回答/承接）
3. 情境匹配（20分）: 语弹的语境是否适合当前对话场景
4. 情感契合（10分）: 如果需要，语弹情感是否契合对话氛围
{intent_guidance}

评分标准：
- 90-100: 完美匹配，非常恰当的回复
- 70-89: 良好匹配，可以作为回复
- 50-69: 一般匹配，勉强可用
- 30-49: 较弱匹配，不太适合
- 0-29: 不匹配，完全不合适

请只返回JSON格式：
{{"score": 分数, "reasoning": "简要评分理由"}}

例如：
用户输入: "最近天气怎么样"
候选语弹: "北京今天下雨了"
返回: {{"score": 85, "reasoning": "语弹直接回答了天气问题，语义相关且适合作为回复"}}

用户输入: "北京今天下雨了"
候选语弹: "北京今天下雨了"
返回: {{"score": 25, "reasoning": "语弹只是重复用户的话，不是合适的回复"}}
"""

    def _parse_relevance_response(self, response: str) -> tuple[float, str]:
        """
        解析LLM的匹配度响应
        """
        import json
        import re

        try:
            # 尝试直接解析JSON
            # 先尝试提取JSON块
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                data = json.loads(json_match.group())
                score = float(data.get("score", 0)) / 100.0  # 转换为0-1范围
                reasoning = data.get("reasoning", "")
                return max(0.0, min(1.0, score)), reasoning
        except Exception as e:
            logger.warning(f"解析匹配度响应失败: {e}, 响应: {response}")

        # 解析失败，返回默认低分
        return 0.0, "无法解析评估结果"


# 全局服务实例
relevance_service = RelevanceService()


async def calculate_relevance(
    user_query: str,
    segment_text: str,
    segment_emotion: Optional[str] = None
) -> RelevanceScore:
    """便捷函数：计算单个语弹的匹配度"""
    return await relevance_service.calculate_relevance(
        user_query, segment_text, segment_emotion
    )


async def batch_calculate_relevance(
    user_query: str,
    segments: List[Dict[str, Any]]
) -> List[Tuple[Dict[str, Any], RelevanceScore]]:
    """便捷函数：批量计算匹配度"""
    return await relevance_service.batch_calculate_relevance(user_query, segments)
