"""
匹配度服务 - 评估语弹作为回复的合适程度

从"相似度"转向"匹配度"：
- 相似度：文本内容的相似程度（cosine similarity）
- 匹配度：语弹作为回复的合适程度（question-answer relevance）
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ai_models.llm_service import LLMService

logger = logging.getLogger(__name__)


@dataclass
class RelevanceScore:
    """匹配度评分结果"""
    score: float  # 0-1 的匹配度分数
    reasoning: str  # 评分理由
    is_match: bool  # 是否达到匹配门槛


class RelevanceService:
    """
    匹配度评估服务
    使用LLM判断语弹是否适合作为对用户输入的回复
    """

    def __init__(self):
        self.llm_service = LLMService()

    async def calculate_relevance(
        self,
        user_query: str,
        segment_text: str,
        segment_emotion: Optional[str] = None
    ) -> RelevanceScore:
        """
        计算语弹作为回复的匹配度

        Args:
            user_query: 用户输入（问题或陈述）
            segment_text: 语弹的转录文本
            segment_emotion: 语弹的情感标签（可选）

        Returns:
            RelevanceScore: 匹配度评分结果
        """
        # 构建评估提示词
        prompt = self._build_relevance_prompt(user_query, segment_text, segment_emotion)

        try:
            # 调用LLM进行评估
            result = await self.llm_service.generate_chat_response(
                query=prompt,
                system_prompt="你是一个专业的语义匹配评估专家。请根据用户输入和候选语弹，评估语弹作为回复的匹配程度。只返回JSON格式的评分结果。",
                temperature=0.3,
                max_tokens=200
            )

            # 提取回复内容
            response = result.get("reply", "") if result.get("success") else ""

            # 解析响应
            score, reasoning = self._parse_relevance_response(response)

            return RelevanceScore(
                score=score,
                reasoning=reasoning,
                is_match=score >= 0.48  # 使用与相似度相同的阈值
            )
        except Exception as e:
            logger.error(f"匹配度计算失败: {e}")
            # 失败时返回低匹配度，但不阻断流程
            return RelevanceScore(
                score=0.0,
                reasoning=f"评估失败: {str(e)}",
                is_match=False
            )

    async def batch_calculate_relevance(
        self,
        user_query: str,
        segments: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], RelevanceScore]]:
        """
        批量计算多个语弹的匹配度

        Args:
            user_query: 用户输入
            segments: 语弹列表，每个包含 text, emotion 等字段

        Returns:
            按匹配度排序的 (语弹, 匹配度) 列表
        """
        results = []

        for segment in segments:
            score = await self.calculate_relevance(
                user_query=user_query,
                segment_text=segment.get("transcription", ""),
                segment_emotion=segment.get("emotion")
            )
            results.append((segment, score))

        # 按匹配度降序排序
        results.sort(key=lambda x: x[1].score, reverse=True)
        return results

    def _build_relevance_prompt(
        self,
        user_query: str,
        segment_text: str,
        segment_emotion: Optional[str] = None
    ) -> str:
        """
        构建匹配度评估提示词
        """
        emotion_info = f"\n语弹情感: {segment_emotion}" if segment_emotion else ""

        return f"""请评估以下语弹作为回复的匹配程度。

用户输入: "{user_query}"

候选语弹: "{segment_text}"{emotion_info}

请从以下维度评估匹配度（0-100分）：
1. 语义相关性（40分）: 语弹内容是否与用户输入的话题相关
2. 回复 appropriateness（30分）: 语弹是否适合作为对用户输入的回应（不是重复，而是回答/承接）
3. 情境匹配（20分）: 语弹的语境是否适合当前对话场景
4. 情感契合（10分）: 如果需要，语弹情感是否契合对话氛围

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
