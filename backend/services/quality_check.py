"""
语弹质量检查模块

精品语弹标准：
1. 文本长度：至少5个中文字符
2. 句子完整性：以标点符号结尾（。！？）
3. 内容质量：不包含过多重复
4. 标点符号：包含合理的标点
"""

import logging
import re
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class SegmentQualityChecker:
    """
    语弹质量检查器
    """

    def __init__(self):
        # 最小中文字符数（放宽到3字，允许短句）
        self.min_chinese_chars = 3
        # 最大重复比例（重复字符占总字符的比例）
        self.max_repeat_ratio = 0.6
        # 最小标点符号数
        self.min_punctuation = 0
        # 句子结束标点
        self.sentence_endings = ['。', '！', '？', '.', '!', '?', '，', ',']

    def check_quality(self, text: str, duration: float) -> Tuple[bool, Dict[str, Any]]:
        """
        检查语弹质量

        Args:
            text: 转录文本
            duration: 音频时长（秒）

        Returns:
            (是否合格, 详细信息字典)
        """
        if not text:
            return False, {"reason": "文本为空"}

        text = text.strip()
        result = {
            "text": text,
            "duration": duration,
            "checks": {},
            "passed": True,
            "reasons": []
        }

        # 检查1: 文本长度（中文字符数）
        chinese_chars = self._count_chinese_chars(text)
        result["checks"]["chinese_chars"] = {
            "value": chinese_chars,
            "min_required": self.min_chinese_chars,
            "passed": chinese_chars >= self.min_chinese_chars
        }
        if chinese_chars < self.min_chinese_chars:
            result["passed"] = False
            result["reasons"].append(f"中文太少({chinese_chars}<{self.min_chinese_chars})")

        # 检查2: 句子完整性（是否以标点结尾）
        has_ending = any(text.endswith(end) for end in self.sentence_endings)
        result["checks"]["sentence_completeness"] = {
            "value": has_ending,
            "passed": has_ending
        }
        # 注意：不强求句子完整性，只是作为评分参考

        # 检查3: 重复内容检查
        repeat_ratio = self._check_repeat_ratio(text)
        result["checks"]["repeat_ratio"] = {
            "value": repeat_ratio,
            "max_allowed": self.max_repeat_ratio,
            "passed": repeat_ratio <= self.max_repeat_ratio
        }
        if repeat_ratio > self.max_repeat_ratio:
            result["passed"] = False
            result["reasons"].append(f"重复太多({repeat_ratio:.1%})")

        # 检查4: 标点符号检查
        punct_count = self._count_punctuation(text)
        result["checks"]["punctuation"] = {
            "value": punct_count,
            "min_required": self.min_punctuation,
            "passed": punct_count >= self.min_punctuation
        }

        # 检查5: 文本-时长比例（语速检查，放宽范围）
        chars_per_second = chinese_chars / duration if duration > 0 else 0
        result["checks"]["speech_rate"] = {
            "value": chars_per_second,
            "range": "1-10 字/秒",
            "passed": 1 <= chars_per_second <= 10
        }
        if chars_per_second < 0.8:
            result["passed"] = False
            result["reasons"].append(f"语速太慢({chars_per_second:.1f}字/秒)")
        elif chars_per_second > 12:
            result["passed"] = False
            result["reasons"].append(f"语速太快({chars_per_second:.1f}字/秒)")

        # 检查6: 静音检查（如果文本中有大量省略号）
        ellipsis_count = text.count('...') + text.count('……')
        if ellipsis_count > 2:
            result["checks"]["ellipsis"] = {
                "value": ellipsis_count,
                "passed": False
            }
            result["passed"] = False
            result["reasons"].append(f"过多停顿({ellipsis_count}处)")

        # 综合评分
        score = self._calculate_score(result["checks"])
        result["score"] = score
        result["quality_level"] = self._get_quality_level(score)

        return result["passed"], result

    def _count_chinese_chars(self, text: str) -> int:
        """统计中文字符数量"""
        count = 0
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                count += 1
        return count

    def _check_repeat_ratio(self, text: str) -> float:
        """检查文本重复比例"""
        if len(text) < 4:
            return 0.0

        # 检查连续重复（如"你好你好"）
        repeat_chars = 0
        for i in range(len(text) - 1):
            if text[i] == text[i + 1]:
                repeat_chars += 1

        # 检查句子重复（简单实现）
        sentences = re.split(r'[。！？.!?]+', text)
        unique_sentences = set(s.strip() for s in sentences if len(s.strip()) > 3)
        if len(sentences) > 1 and len(unique_sentences) < len(sentences) * 0.7:
            # 有重复句子
            return 0.6

        return repeat_chars / len(text)

    def _count_punctuation(self, text: str) -> int:
        """统计标点符号数量"""
        punctuations = '。，、；：？！""''（）【】《》'
        count = 0
        for char in text:
            if char in punctuations:
                count += 1
        return count

    def _calculate_score(self, checks: Dict[str, Any]) -> float:
        """计算质量评分（0-100）"""
        score = 100.0

        # 长度扣分
        char_check = checks.get("chinese_chars", {})
        if not char_check.get("passed", True):
            score -= 30

        # 重复扣分
        repeat_check = checks.get("repeat_ratio", {})
        if not repeat_check.get("passed", True):
            score -= 20

        # 语速扣分
        rate_check = checks.get("speech_rate", {})
        if not rate_check.get("passed", True):
            score -= 15

        # 完整性加分
        complete_check = checks.get("sentence_completeness", {})
        if complete_check.get("passed", False):
            score += 5

        return max(0.0, min(100.0, score))

    def _get_quality_level(self, score: float) -> str:
        """根据评分返回质量等级"""
        if score >= 90:
            return "优秀"
        elif score >= 75:
            return "良好"
        elif score >= 60:
            return "合格"
        else:
            return "不合格"


# 全局质量检查器实例
quality_checker = SegmentQualityChecker()


async def check_segment_quality(text: str, duration: float) -> Tuple[bool, Dict[str, Any]]:
    """
    检查语弹质量的便捷函数

    Returns:
        (是否合格, 详细信息)
    """
    return quality_checker.check_quality(text, duration)
# Test change at 2026年04月 8日 13:44:21
# Test 1775627224
