#!/usr/bin/env python3
"""
生成有效的提示词 - 基于现有音频片段内容生成肯定能匹配到音频的提示词
"""
import sys
import logging
import asyncio
from pathlib import Path
from typing import List, Tuple, Dict, Any
import pymysql

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings
from ai_models.nlp_service import get_text_vector
from services.search_service import search_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_audio_segment_samples():
    """获取音频片段样本用于分析"""
    connection = None
    try:
        # 连接到MySQL数据库
        connection = pymysql.connect(
            host='localhost',
            user='soundverse',
            password='password',
            database='soundverse',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )

        with connection.cursor() as cursor:
            # 查询转录文本样本
            sql = """
            SELECT DISTINCT
                LEFT(transcription, 200) as text_sample,
                LENGTH(transcription) as text_length
            FROM audio_segments
            WHERE transcription IS NOT NULL
              AND LENGTH(transcription) > 10
            ORDER BY text_length DESC
            LIMIT 50
            """
            cursor.execute(sql)
            samples = cursor.fetchall()

            logger.info(f"获取到 {len(samples)} 个文本样本")
            return [sample['text_sample'] for sample in samples]

    except Exception as e:
        logger.error(f"查询数据库失败: {str(e)}")
        return []
    finally:
        if connection:
            connection.close()


def extract_key_phrases(text_samples: List[str]):
    """从文本样本中提取关键短语"""
    # 简单提取：获取包含2-4个词的常见短语
    all_words = []
    for text in text_samples:
        if text:
            # 中文文本，按字符分割（简单处理）
            words = []
            current_word = ""
            for char in text:
                if char in '，。！？；：,.!?;:、 ':
                    if current_word:
                        words.append(current_word)
                        current_word = ""
                else:
                    current_word += char
            if current_word:
                words.append(current_word)
            all_words.extend(words)

    # 统计词频
    from collections import Counter
    word_counts = Counter(all_words)

    # 获取高频词
    high_freq_words = [word for word, count in word_counts.most_common(30) if len(word) > 1]

    logger.info(f"高频词: {high_freq_words[:20]}")
    return high_freq_words


def generate_prompts_from_samples(text_samples: List[str]) -> List[str]:
    """从文本样本生成提示词"""
    prompts = []

    # 分析样本主题
    themes = set()
    for text in text_samples[:20]:  # 分析前20个样本
        if not text:
            continue

        # 简单主题提取
        if '张慧欣' in text:
            themes.add('张慧欣的故事')
        if '跨省通勤' in text:
            themes.add('跨省通勤')
        if '京津冀' in text:
            themes.add('京津冀协同发展')
        if '北京' in text and '河北' in text:
            themes.add('北京河北生活')
        if '交通' in text or '公交' in text:
            themes.add('交通出行')
        if '家庭' in text or '爱人' in text or '女儿' in text:
            themes.add('家庭生活')
        if '工作' in text:
            themes.add('工作')
        if '就医' in text:
            themes.add('医疗')

    logger.info(f"识别到的主题: {list(themes)}")

    # 基于主题生成提示词
    theme_prompts = [
        "张慧欣是谁？",
        "跨省通勤是什么体验？",
        "京津冀协同发展对普通人有什么影响？",
        "北京和河北之间的交通方便吗？",
        "家庭和工作如何平衡？",
        "跨省通勤有哪些困难？",
        "二零一八年发生了什么重要的事？",
        "丰台区六里桥东公交站在哪里？",
        "京津冀协同发展带来了哪些变化？",
        "张慧欣的日常生活是怎样的？",
    ]

    # 从文本样本直接生成提示词
    for text in text_samples[:10]:
        if len(text) > 20:
            # 提取关键句子作为提示词
            sentences = text.split('。')
            for sentence in sentences:
                if len(sentence) > 10 and len(sentence) < 50:
                    prompt = sentence.strip()
                    if prompt and ' ' not in prompt:  # 简单过滤
                        prompts.append(prompt + "？")

    # 组合提示词
    all_prompts = theme_prompts + prompts[:10]  # 限制数量

    # 去重
    unique_prompts = []
    seen = set()
    for prompt in all_prompts:
        if prompt not in seen:
            seen.add(prompt)
            unique_prompts.append(prompt)

    return unique_prompts[:15]  # 返回前15个


async def test_prompt_effectiveness(prompt: str) -> Tuple[bool, float]:
    """测试提示词的有效性（是否能匹配到音频）"""
    try:
        # 获取查询向量
        query_vector = await get_text_vector(prompt, text_type="query")
        if not query_vector:
            return False, 0.0

        # 搜索相似片段
        search_results = await search_service.search_similar_segments(
            query_vector=query_vector,
            top_k=1,
            similarity_threshold=0.0  # 设置阈值为0以查看所有结果
        )

        if search_results:
            best_similarity = search_results[0][1]
            is_effective = best_similarity >= settings.AUDIO_REPLY_THRESHOLD
            return is_effective, best_similarity
        else:
            return False, 0.0

    except Exception as e:
        logger.error(f"测试提示词失败: {prompt}, 错误: {str(e)}")
        return False, 0.0


async def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("  生成有效的提示词")
    logger.info("=" * 60)

    # 步骤1: 获取音频片段样本
    logger.info("步骤1: 获取音频片段样本...")
    text_samples = get_audio_segment_samples()

    if not text_samples:
        logger.error("无法获取音频片段样本")
        return 1

    logger.info(f"获取到 {len(text_samples)} 个文本样本")

    # 步骤2: 分析样本并生成提示词
    logger.info("步骤2: 分析样本并生成提示词...")
    prompts = generate_prompts_from_samples(text_samples)

    logger.info(f"生成 {len(prompts)} 个候选提示词:")
    for i, prompt in enumerate(prompts, 1):
        logger.info(f"  {i:2d}. {prompt}")

    # 步骤3: 初始化搜索服务
    logger.info("步骤3: 初始化搜索服务...")
    await search_service.initialize()

    # 步骤4: 测试提示词有效性
    logger.info("步骤4: 测试提示词有效性...")
    effective_prompts = []

    for prompt in prompts:
        logger.info(f"测试提示词: '{prompt}'")
        is_effective, similarity = await test_prompt_effectiveness(prompt)

        if is_effective:
            logger.info(f"  [有效] 相似度: {similarity:.4f} ≥ 阈值 {settings.AUDIO_REPLY_THRESHOLD}")
            effective_prompts.append((prompt, similarity))
        else:
            logger.info(f"  [无效] 相似度: {similarity:.4f} < 阈值 {settings.AUDIO_REPLY_THRESHOLD}")

    # 步骤5: 输出结果
    logger.info("\n" + "=" * 60)
    logger.info("  生成结果")
    logger.info("=" * 60)

    if effective_prompts:
        # 按相似度排序
        effective_prompts.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"找到 {len(effective_prompts)} 个有效提示词:")
        for i, (prompt, similarity) in enumerate(effective_prompts, 1):
            logger.info(f"  {i:2d}. {prompt} (相似度: {similarity:.4f})")

        # 生成JavaScript数组格式（用于前端）
        logger.info("\nJavaScript数组格式:")
        js_array = "const quickQuestions = [\n"
        for prompt, similarity in effective_prompts[:8]:  # 取前8个
            js_array += f'  "{prompt}",\n'
        js_array += "];"
        logger.info(js_array)

        # 生成JSON格式
        logger.info("\nJSON格式:")
        import json
        json_data = {
            "effective_prompts": [
                {"prompt": prompt, "similarity": similarity}
                for prompt, similarity in effective_prompts[:8]
            ],
            "count": len(effective_prompts[:8]),
            "threshold": settings.AUDIO_REPLY_THRESHOLD
        }
        logger.info(json.dumps(json_data, ensure_ascii=False, indent=2))
    else:
        logger.warning("未找到有效提示词，需要调整生成策略")

    # 步骤6: 提供建议
    logger.info("\n" + "=" * 60)
    logger.info("  使用建议")
    logger.info("=" * 60)
    logger.info("1. 将有效提示词添加到前端聊天页面的预置问题中")
    logger.info("2. 修改前端代码，确保在消息较少时显示预置问题")
    logger.info("3. 定期更新提示词以匹配数据库内容变化")
    logger.info("4. 阈值设置: 当前为 0.70，可适当调整以提高/降低匹配严格度")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)