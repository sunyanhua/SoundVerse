"""
歌曲/音乐内容检测服务

基于音频特征识别广播节目中的歌曲片段：
1. 语速均匀性检测（歌曲通常语速均匀）
2. 停顿模式分析（歌曲有规律的节拍停顿）
3. 频谱特征分析（歌声有特定频谱模式）
4. ASR文本特征（歌词通常有韵律特征）
"""

import logging
import math
from typing import Dict, Any, Tuple, List
from pathlib import Path

import numpy as np
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

logger = logging.getLogger(__name__)


class MusicDetector:
    """
    歌曲/音乐内容检测器
    """

    def __init__(self):
        # 语速检测阈值
        self.speech_rate_min = 0.5  # 最小语速（字/秒）
        self.speech_rate_max = 8.0  # 最大语速（字/秒）

        # 停顿模式检测阈值
        self.singing_pause_min = 0.15  # 歌唱中最小停顿（秒）
        self.singing_pause_max = 0.8   # 歌唱中最大停顿（秒）
        self.singing_pause_ratio = 0.3  # 歌唱中停顿占比

        # 频谱分析阈值
        self.pitch_variance_threshold = 0.4  # 音高变化方差阈值（歌曲通常变化更平滑）

        # 综合判定阈值
        self.music_score_threshold = 0.65  # 判定为歌曲的分数阈值

    async def detect_music_segment(
        self,
        audio_file_path: str,
        start_time: float,
        end_time: float,
        text: str = "",
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        检测指定时间段内的音频是否为歌曲/音乐

        Args:
            audio_file_path: 音频文件路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            text: ASR转录文本

        Returns:
            (是否为歌曲, 置信度分数, 详细信息字典)
        """
        try:
            duration = end_time - start_time

            # 加载音频片段
            audio = AudioSegment.from_file(audio_file_path)
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            segment = audio[start_ms:end_ms]

            # 提取音频特征
            features = await self._extract_features(segment, text, duration)

            # 计算歌曲得分
            is_music, score, details = self._calculate_music_score(features)

            return is_music, score, details

        except Exception as e:
            logger.error(f"歌曲检测失败: {e}")
            return False, 0.0, {"error": str(e)}

    async def _extract_features(
        self,
        segment: AudioSegment,
        text: str,
        duration: float,
    ) -> Dict[str, Any]:
        """
        提取音频特征
        """
        features = {
            "duration": duration,
            "text": text,
        }

        # 1. 语速特征（基于文本长度和时长）
        if text and duration > 0:
            chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
            speech_rate = chinese_chars / duration
            features["speech_rate"] = speech_rate
            features["chinese_chars"] = chinese_chars
        else:
            features["speech_rate"] = 0
            features["chinese_chars"] = 0

        # 2. 停顿模式分析
        pause_features = self._analyze_pause_pattern(segment)
        features.update(pause_features)

        # 3. 音量/能量特征
        energy_features = self._analyze_energy_pattern(segment)
        features.update(energy_features)

        # 4. 频谱特征（简化版，使用能量分布）
        spectral_features = self._analyze_spectral_pattern(segment)
        features.update(spectral_features)

        # 5. 文本韵律特征
        text_features = self._analyze_text_pattern(text)
        features.update(text_features)

        return features

    def _analyze_pause_pattern(self, segment: AudioSegment) -> Dict[str, Any]:
        """
        分析停顿模式

        歌曲特征：
        - 停顿相对均匀（在0.2-0.6秒之间）
        - 停顿出现频率较高（占时长的20-40%）
        """
        # 检测非静音区间（即语音区间）
        nonsilent_ranges = detect_nonsilent(
            segment,
            min_silence_len=50,  # 50ms以上的静音才被视为停顿
            silence_thresh=-40,  # -40dB以下视为静音
        )

        duration_ms = len(segment)
        duration_sec = duration_ms / 1000.0

        if not nonsilent_ranges or len(nonsilent_ranges) < 2:
            return {
                "pause_count": 0,
                "avg_pause_duration": 0,
                "pause_variance": 0,
                "pause_ratio": 0,
                "is_regular_pause": False,
            }

        # 计算停顿区间
        pauses = []
        for i in range(len(nonsilent_ranges) - 1):
            pause_start = nonsilent_ranges[i][1]
            pause_end = nonsilent_ranges[i + 1][0]
            pause_duration = (pause_end - pause_start) / 1000.0  # 转换为秒
            if pause_duration >= 0.05:  # 只记录50ms以上的停顿
                pauses.append(pause_duration)

        if not pauses:
            return {
                "pause_count": 0,
                "avg_pause_duration": 0,
                "pause_variance": 0,
                "pause_ratio": 0,
                "is_regular_pause": False,
            }

        # 计算停顿统计特征
        avg_pause = np.mean(pauses)
        pause_variance = np.var(pauses) if len(pauses) > 1 else 0
        total_pause_time = sum(pauses)
        pause_ratio = total_pause_time / duration_sec

        # 检测是否规律（方差小表示规律）
        is_regular = pause_variance < 0.1 and len(pauses) >= 2

        # 检测是否在歌唱停顿范围内
        singing_like_pauses = sum(
            1 for p in pauses
            if self.singing_pause_min <= p <= self.singing_pause_max
        )
        singing_pause_ratio = singing_like_pauses / len(pauses) if pauses else 0

        return {
            "pause_count": len(pauses),
            "avg_pause_duration": avg_pause,
            "pause_variance": pause_variance,
            "pause_ratio": pause_ratio,
            "is_regular_pause": is_regular,
            "singing_pause_ratio": singing_pause_ratio,
        }

    def _analyze_energy_pattern(self, segment: AudioSegment) -> Dict[str, Any]:
        """
        分析能量/音量模式

        歌曲特征：
        - 音量相对平稳（动态范围较小）
        - 有明显的节奏感（能量周期性变化）
        """
        # 将音频分成小窗口分析能量
        window_ms = 100  # 100ms窗口
        energies = []

        for i in range(0, len(segment), window_ms):
            window = segment[i:i + window_ms]
            # 计算RMS能量（dB）
            rms = window.rms
            if rms > 0:
                db = 20 * math.log10(rms)
                energies.append(db)
            else:
                energies.append(-100)

        if not energies:
            return {
                "energy_variance": 0,
                "energy_range": 0,
                "energy_rhythm_score": 0,
            }

        # 计算能量统计特征
        energy_variance = np.var(energies)
        energy_range = max(energies) - min(energies)

        # 检测节奏性（通过自相关）
        rhythm_score = self._detect_rhythm(energies)

        return {
            "energy_variance": energy_variance,
            "energy_range": energy_range,
            "energy_rhythm_score": rhythm_score,
        }

    def _detect_rhythm(self, energies: List[float]) -> float:
        """
        检测能量序列的节奏性（周期性）

        返回值：0-1，越高表示越有节奏性
        """
        if len(energies) < 20:
            return 0.0

        # 计算一阶差分
        diff = np.diff(energies)

        # 计算自相关（检测周期性）
        def autocorr(x, max_lags=50):
            """计算自相关"""
            x = np.array(x)
            x = x - np.mean(x)
            autocorr = np.correlate(x, x, mode='full')
            autocorr = autocorr[len(autocorr)//2:]
            if autocorr[0] != 0:
                autocorr = autocorr / autocorr[0]
            return autocorr[:max_lags]

        ac = autocorr(diff, max_lags=min(50, len(diff) // 2))

        # 寻找峰值（排除lag=0）
        if len(ac) > 5:
            # 找局部最大值
            peaks = []
            for i in range(3, len(ac) - 3):
                if ac[i] > ac[i-1] and ac[i] > ac[i-2] and ac[i] > ac[i+1] and ac[i] > ac[i+2]:
                    if ac[i] > 0.1:  # 阈值
                        peaks.append(ac[i])

            if peaks:
                # 有清晰的峰值表示有节奏性
                return min(1.0, np.mean(peaks) * 2)

        return 0.0

    def _analyze_spectral_pattern(self, segment: AudioSegment) -> Dict[str, Any]:
        """
        分析频谱模式（简化版）

        歌曲特征：
        - 频谱能量分布相对集中（人声频段）
        - 频谱变化相对平滑
        """
        # 使用高频和低频能量比作为简单特征
        # 歌曲通常在中频（人声）有集中能量

        # 将音频转为单声道并降低采样率以简化分析
        mono_segment = segment.set_channels(1)

        # 简单能量分析
        samples = np.array(mono_segment.get_array_of_samples())

        if len(samples) == 0:
            return {
                "spectral_centroid": 0,
                "spectral_variance": 0,
            }

        # 计算简单频谱特征（使用零交叉率近似高频含量）
        zero_crossings = np.sum(np.diff(np.sign(samples)) != 0)
        zcr = zero_crossings / len(samples) if len(samples) > 0 else 0

        return {
            "zero_crossing_rate": zcr,
        }

    def _analyze_text_pattern(self, text: str) -> Dict[str, Any]:
        """
        分析文本韵律模式

        歌词特征：
        - 重复性高（副歌重复）
        - 有韵律（押韵）
        - 句子长度相对均匀
        """
        if not text:
            return {
                "text_repetition": 0,
                "sentence_length_variance": 0,
                "rhyme_indicator": 0,
            }

        # 分句
        sentences = [s.strip() for s in text.split('，') if s.strip()]
        if not sentences:
            sentences = [text]

        # 计算句子长度方差（歌词通常长度均匀）
        sentence_lengths = [len(s) for s in sentences]
        length_variance = np.var(sentence_lengths) if len(sentence_lengths) > 1 else 0

        # 检测重复（简单检测）
        repetition_score = 0
        if len(sentences) >= 2:
            for i in range(len(sentences)):
                for j in range(i + 1, len(sentences)):
                    s1 = sentences[i]
                    s2 = sentences[j]
                    # 计算相似度
                    if len(s1) > 3 and len(s2) > 3:
                        # 简单相似度：共同子串长度
                        common = self._longest_common_substring(s1, s2)
                        if len(common) >= 3:
                            repetition_score = max(repetition_score, len(common) / max(len(s1), len(s2)))

        # 简单押韵检测（检查结尾字的韵母）
        rhyme_score = self._detect_rhyme(sentences)

        return {
            "text_repetition": repetition_score,
            "sentence_length_variance": length_variance,
            "rhyme_indicator": rhyme_score,
        }

    def _longest_common_substring(self, s1: str, s2: str) -> str:
        """计算最长公共子串"""
        if not s1 or not s2:
            return ""

        m, n = len(s1), len(s2)
        max_len = 0
        end_pos = 0

        # 动态规划
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                    if dp[i][j] > max_len:
                        max_len = dp[i][j]
                        end_pos = i
                else:
                    dp[i][j] = 0

        return s1[end_pos - max_len:end_pos] if max_len > 0 else ""

    def _detect_rhyme(self, sentences: List[str]) -> float:
        """
        简单押韵检测

        返回0-1的分数
        """
        if len(sentences) < 2:
            return 0.0

        # 获取每个句子的最后一个字
        ending_chars = []
        for s in sentences:
            # 提取中文字符
            chinese_chars = [c for c in s if '\u4e00' <= c <= '\u9fff']
            if chinese_chars:
                ending_chars.append(chinese_chars[-1])

        if len(ending_chars) < 2:
            return 0.0

        # 简单韵母分组（简化版，实际应使用拼音）
        # 这里使用常见押韵字的简单映射
        rhyme_groups = {
            'a': ['啊', '呀', '啦', '吧', '吗', '嘛', '咖', '沙', '他', '她', '它'],
            'o': ['哦', '波', '坡', '摸', '佛', '多', '托', '诺', '罗', '哥', '克'],
            'e': ['呢', '了', '么', '得', '的', '特', '呢', '乐', '格', '可', '和'],
            'i': ['一', '以', '已', '意', '义', '亿', '里', '你', '体', '起', '去', '离', '迷', '西'],
            'u': ['不', '部', '步', '布', '无', '五', '物', '舞', '图', '苦', '古', '乎', '湖', '数'],
            'ü': ['去', '取', '区', '曲', '需', '许', '虚', '鱼', '雨', '语', '遇', '女', '绿', '旅'],
            'ai': ['爱', '在', '来', '开', '海', '还', '改', '白', '才', '代', '太', '外', '快'],
            'ei': ['诶', '被', '给', '北', '美', '类', '每', '内', '雷', '非', '飞', '肥'],
            'ao': ['奥', '好', '到', '道', '老', '小', '少', '早', '叫', '高', '脑', '毛'],
            'ou': ['欧', '有', '又', '友', '右', '就', '手', '头', '后', '周', '楼', '口'],
            'an': ['安', '按', '暗', '案', '看', '干', '感', '敢', '半', '班', '然', '前', '边'],
            'en': ['恩', '本', '们', '门', '分', '份', '人', '任', '真', '深', '身', '神'],
            'ang': ['昂', '让', '上', '想', '向', '香', '相', '长', '常', '唱', '强', '样'],
            'eng': ['鞥', '成', '城', '程', '声', '生', '升', '正', '等', '更', '能', '冷'],
        }

        # 统计押韵对数
        rhyme_pairs = 0
        total_pairs = 0

        for i in range(len(ending_chars)):
            for j in range(i + 1, len(ending_chars)):
                total_pairs += 1
                c1, c2 = ending_chars[i], ending_chars[j]

                # 检查是否在同一个韵组
                for group in rhyme_groups.values():
                    if c1 in group and c2 in group:
                        rhyme_pairs += 1
                        break

        return rhyme_pairs / total_pairs if total_pairs > 0 else 0.0

    def _calculate_music_score(self, features: Dict[str, Any]) -> Tuple[bool, float, Dict[str, Any]]:
        """
        计算歌曲得分

        综合多个特征判断是否为歌曲
        """
        scores = []
        details = {}

        # 1. 停顿模式评分（歌曲停顿相对规律）
        pause_variance = features.get("pause_variance", 0)
        is_regular_pause = features.get("is_regular_pause", False)
        singing_pause_ratio = features.get("singing_pause_ratio", 0)

        if pause_variance < 0.05 and is_regular_pause:
            pause_score = 0.8
        elif pause_variance < 0.1 and is_regular_pause:
            pause_score = 0.6
        elif singing_pause_ratio > 0.5:
            pause_score = 0.5
        else:
            pause_score = 0.2

        scores.append(pause_score)
        details["pause_pattern_score"] = pause_score

        # 2. 能量节奏评分
        rhythm_score = features.get("energy_rhythm_score", 0)
        energy_score = min(1.0, rhythm_score * 1.5)  # 放大节奏信号
        scores.append(energy_score)
        details["energy_rhythm_score"] = energy_score

        # 3. 语速评分（歌曲语速通常较慢且均匀）
        speech_rate = features.get("speech_rate", 0)
        if 1.0 <= speech_rate <= 3.5:  # 歌曲常见语速范围
            rate_score = 0.6
        elif 3.5 < speech_rate <= 6.0:
            rate_score = 0.3
        else:
            rate_score = 0.1

        scores.append(rate_score)
        details["speech_rate_score"] = rate_score

        # 4. 文本重复性评分（歌词常有重复）
        text_repetition = features.get("text_repetition", 0)
        repetition_score = min(1.0, text_repetition * 2)
        scores.append(repetition_score)
        details["text_repetition_score"] = repetition_score

        # 5. 押韵评分
        rhyme_indicator = features.get("rhyme_indicator", 0)
        rhyme_score = min(1.0, rhyme_indicator * 2)
        scores.append(rhyme_score)
        details["rhyme_score"] = rhyme_score

        # 计算加权总分
        weights = [0.25, 0.25, 0.15, 0.2, 0.15]  # 停顿、节奏、语速、重复、押韵
        total_score = sum(s * w for s, w in zip(scores, weights))

        # 判定是否为歌曲
        is_music = total_score >= self.music_score_threshold

        details["total_score"] = total_score
        details["threshold"] = self.music_score_threshold
        details["features"] = {
            k: v for k, v in features.items()
            if k not in ["text"]  # 排除长文本
        }

        return is_music, total_score, details


# 全局检测器实例
music_detector = MusicDetector()


async def detect_music_in_segment(
    audio_file_path: str,
    start_time: float,
    end_time: float,
    text: str = "",
) -> Tuple[bool, float, Dict[str, Any]]:
    """
    便捷函数：检测音频片段是否为歌曲

    Returns:
        (是否为歌曲, 置信度分数, 详细信息)
    """
    return await music_detector.detect_music_segment(
        audio_file_path, start_time, end_time, text
    )


async def filter_music_segments(
    segments: List[Tuple[float, float, str]],
    audio_file_path: str,
    threshold: float = 0.65,
) -> Tuple[List[Tuple[float, float, str]], List[Dict[str, Any]]]:
    """
    过滤掉检测为歌曲的片段

    Args:
        segments: 音频片段列表 [(start, end, text), ...]
        audio_file_path: 音频文件路径
        threshold: 判定为歌曲的阈值

    Returns:
        (过滤后的片段列表, 被过滤的片段信息列表)
    """
    filtered_segments = []
    music_segments_info = []

    for start, end, text in segments:
        is_music, score, details = await detect_music_in_segment(
            audio_file_path, start, end, text
        )

        if is_music and score >= threshold:
            logger.info(f"检测到歌曲片段: {start:.2f}s-{end:.2f}s, 得分: {score:.2f}")
            music_segments_info.append({
                "start": start,
                "end": end,
                "text": text,
                "score": score,
                "details": details,
            })
        else:
            filtered_segments.append((start, end, text))

    if music_segments_info:
        logger.info(f"歌曲检测完成: 过滤 {len(music_segments_info)} 个歌曲片段，保留 {len(filtered_segments)} 个语音片段")
    else:
        logger.info(f"歌曲检测完成: 未检测到歌曲片段，保留全部 {len(filtered_segments)} 个片段")

    return filtered_segments, music_segments_info
