#!/usr/bin/env python3
"""
修改 chat_service.py，使用匹配度替换相似度
"""

import re

# 读取文件
with open('/app/services/chat_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 添加 relevance_service 导入
import_section = '''from services.prompt_generation_service import generate_prompts_for_audio_segment
from services.conversational_prompt_service import (
    generate_conversational_suggestions_from_audio,
    enrich_chat_suggestions_with_audio_context,
    get_default_conversational_suggestions,
)'''

new_import_section = '''from services.prompt_generation_service import generate_prompts_for_audio_segment
from services.conversational_prompt_service import (
    generate_conversational_suggestions_from_audio,
    enrich_chat_suggestions_with_audio_context,
    get_default_conversational_suggestions,
)
from services.relevance_service import relevance_service, RelevanceScore'''

content = content.replace(import_section, new_import_section)

# 2. 找到并替换核心逻辑（从搜索结果处理到返回音频的部分）
old_logic = '''        if search_result.results:
            best_match = search_result.results[0]
            best_similarity = best_match.similarity_score

            # 找出所有达到音频回复门槛的候选音频
            eligible_results = [
                result for result in search_result.results
                if result.similarity_score >= settings.AUDIO_REPLY_THRESHOLD
            ]

            if eligible_results:
                # 选择相似度最高的音频片段（不再随机）
                selected_result = max(eligible_results, key=lambda x: x.similarity_score)
                has_audio_match = True
                audio_segment = selected_result.segment
                best_similarity = selected_result.similarity_score  # 使用选中片段的相似度
                logger.info(f"找到 {len(eligible_results)} 个匹配音频片段（相似度≥{settings.AUDIO_REPLY_THRESHOLD}），选择最高相似度片段ID={audio_segment.id}，相似度 {best_similarity:.4f}")'''

new_logic = '''        if search_result.results:
            # 使用匹配度评估替换相似度判断
            # 对前3个候选语弹进行匹配度评估
            top_candidates = search_result.results[:3]
            best_relevance = None
            best_match = None

            for candidate in top_candidates:
                relevance = await relevance_service.calculate_relevance(
                    user_query=message,
                    segment_text=candidate.segment.transcription or "",
                    segment_emotion=candidate.segment.emotion
                )
                logger.info(f"语弹 {candidate.segment.id} 匹配度: {relevance.score:.2%} - {relevance.reasoning}")

                if best_relevance is None or relevance.score > best_relevance.score:
                    best_relevance = relevance
                    best_match = candidate

            # 检查最佳匹配是否达到门槛
            if best_relevance and best_relevance.is_match:
                has_audio_match = True
                audio_segment = best_match.segment
                best_similarity = best_relevance.score  # 使用匹配度作为分数
                logger.info(f"找到匹配语弹（匹配度≥{settings.AUDIO_REPLY_THRESHOLD}）: 片段ID={audio_segment.id}, 匹配度={best_similarity:.2%}, 理由: {best_relevance.reasoning}")'''

content = content.replace(old_logic, new_logic)

# 3. 修改日志输出，将"相似度"改为"匹配度"或保留上下文
content = content.replace(
    'logger.info(f"返回音频回复: 片段ID={audio_segment.id}, 相似度={best_similarity:.4f}")',
    'logger.info(f"返回音频回复: 片段ID={audio_segment.id}, 匹配度={best_similarity:.2%}")'
)

# 4. 修改建议语弹的日志
content = content.replace(
    'logger.info(f"找到可建议的音频片段: 相似度={best_similarity:.4f} ≥ 建议门槛值={settings.AUDIO_SUGGEST_THRESHOLD}，但 < 播放门槛值={settings.AUDIO_REPLY_THRESHOLD}")',
    'logger.info(f"找到可建议的音频片段: 匹配度={best_similarity:.2%} ≥ 建议门槛值={settings.AUDIO_SUGGEST_THRESHOLD}，但 < 播放门槛值={settings.AUDIO_REPLY_THRESHOLD}")'
)

content = content.replace(
    'logger.info(f"未找到足够匹配的音频: 最高相似度={best_similarity:.4f} < 建议门槛值={settings.AUDIO_SUGGEST_THRESHOLD}")',
    'logger.info(f"未找到足够匹配的音频: 最高匹配度={best_similarity:.2%} < 建议门槛值={settings.AUDIO_SUGGEST_THRESHOLD}")'
)

# 写入文件
with open('/app/services/chat_service.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("chat_service.py 已更新，使用匹配度替换相似度")
