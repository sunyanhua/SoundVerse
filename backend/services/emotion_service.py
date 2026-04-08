"""
情感分析服务

基于文本内容分析语弹的情感倾向
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class EmotionService:
    """
    情感分析服务
    使用规则+关键词的方式分析中文文本情感
    """

    def __init__(self):
        # 情感关键词词典
        self.emotion_keywords = {
            "happy": {
                "keywords": [
                    "开心", "高兴", "快乐", "幸福", "棒", "赞", "优秀", "美好",
                    "喜欢", "爱", "精彩", "愉快", "欢乐", "笑", "哈哈", "嘿嘿",
                    "满意", "舒服", "享受", "轻松", "自在", "惬意", "甜蜜",
                    "感动", "温暖", "温馨", "激动", "兴奋", "期待", "希望"
                ],
                "weight": 1.0
            },
            "sad": {
                "keywords": [
                    "难过", "伤心", "悲伤", "哭", "泪", "痛苦", "失落", "遗憾",
                    "失望", "沮丧", "郁闷", "烦恼", "忧愁", "哀", "凄凉",
                    "孤独", "寂寞", "空虚", "无助", "绝望", "心疼"
                ],
                "weight": 1.0
            },
            "angry": {
                "keywords": [
                    "生气", "愤怒", "讨厌", "恨", "烦", "气", "怒", "火大",
                    "气愤", "恼火", "不满", "抱怨", "谴责", "批评", "骂",
                    "受不了", "忍无可忍", "岂有此理"
                ],
                "weight": 1.0
            },
            "surprise": {
                "keywords": [
                    "惊讶", "震惊", "意外", "居然", "竟然", "没想到", "天哪",
                    "天啊", "哇", "哦", "啊", "不会吧", "真的吗"
                ],
                "weight": 0.8
            },
            "fear": {
                "keywords": [
                    "害怕", "恐惧", "担心", "焦虑", "紧张", "慌", "吓", "怕",
                    "危险", "可怕", "恐怖", "惊慌", "不安"
                ],
                "weight": 0.8
            },
            "neutral": {
                "keywords": [],
                "weight": 0.5
            }
        }

    async def analyze_emotion(self, text: str) -> Dict[str, Any]:
        """
        分析文本情感

        Args:
            text: 要分析的文本

        Returns:
            {
                "emotion": "happy|sad|angry|surprise|fear|neutral",
                "score": float,  # 情感强度 0-1
                "confidence": float,  # 置信度 0-1
                "details": {emotion: score, ...}  # 各情感得分
            }
        """
        if not text or len(text.strip()) < 2:
            return {
                "emotion": "neutral",
                "score": 0.0,
                "confidence": 0.0,
                "details": {k: 0.0 for k in self.emotion_keywords.keys()}
            }

        text = text.strip()

        # 计算各情感得分
        scores = {}
        for emotion, data in self.emotion_keywords.items():
            if emotion == "neutral":
                continue

            score = 0.0
            for keyword in data["keywords"]:
                count = text.count(keyword)
                if count > 0:
                    # 根据关键词长度加权
                    weight = len(keyword) * 0.1 + 0.5
                    score += count * weight * data["weight"]

            scores[emotion] = score

        # 找出得分最高的情感
        if not scores or max(scores.values()) == 0:
            primary_emotion = "neutral"
            emotion_score = 0.0
        else:
            primary_emotion = max(scores, key=scores.get)
            emotion_score = scores[primary_emotion]

        # 计算置信度
        total_score = sum(scores.values())
        if total_score > 0:
            confidence = emotion_score / total_score
        else:
            confidence = 0.0

        # 如果最高得分太低，归为neutral
        if emotion_score < 0.5:
            primary_emotion = "neutral"
            confidence = 1.0 - min(1.0, total_score)

        scores["neutral"] = max(0.0, 1.0 - total_score * 0.3)

        # 英文标签映射到中文
        emotion_cn_map = {
            "happy": "喜悦",
            "sad": "悲伤",
            "angry": "愤怒",
            "surprise": "惊讶",
            "fear": "恐惧",
            "neutral": "平静"
        }

        return {
            "emotion": emotion_cn_map.get(primary_emotion, "平静"),
            "emotion_en": primary_emotion,
            "score": emotion_score,
            "confidence": confidence,
            "details": {emotion_cn_map.get(k, k): v for k, v in scores.items()}
        }

    async def get_emotion_label(self, text: str) -> str:
        """
        获取情感标签（便捷方法）

        Returns:
            情感标签: happy/sad/angry/surprise/fear/neutral
        """
        result = await self.analyze_emotion(text)
        return result["emotion"]

    async def get_sentiment_score(self, text: str) -> float:
        """
        获取情感倾向分数

        Returns:
            -1 到 1 之间的分数，负数表示负面，正数表示正面
        """
        result = await self.analyze_emotion(text)
        emotion = result["emotion"]

        # 映射到 -1 到 1
        sentiment_map = {
            "happy": 1.0,
            "surprise": 0.3,
            "neutral": 0.0,
            "fear": -0.3,
            "sad": -0.7,
            "angry": -0.8
        }

        base_score = sentiment_map.get(emotion, 0.0)
        # 根据置信度调整
        return base_score * result["confidence"]


# 全局情感服务实例
emotion_service = EmotionService()


async def analyze_emotion(text: str) -> Dict[str, Any]:
    """分析情感的便捷函数"""
    return await emotion_service.analyze_emotion(text)


async def get_emotion_label(text: str) -> str:
    """获取情感标签的便捷函数"""
    return await emotion_service.get_emotion_label(text)
# Hot reload test 1775627185
# Hot reload test 2026年04月 8日 13:49:58
# Hot reload test 2026年04月 8日 13:52:46
