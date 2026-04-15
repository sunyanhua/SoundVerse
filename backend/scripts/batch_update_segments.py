#!/usr/bin/env python3
"""
批量更新语弹数据
- 更新 emotion 字段（根据转录文本重新分析）
- 更新 tags 字段（自动提取标签）
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.session import async_session_maker
from shared.models.audio import AudioSegment
from services.emotion_service import analyze_emotion

# 标签提取函数（从 audio_processing_service.py 复制）
def extract_tags_from_text(text: str, max_tags: int = 3) -> list:
    """从转录文本中自动提取标签"""
    if not text or len(text.strip()) < 5:
        return ["日常"]

    tag_keywords = {
        "生活": ["生活", "日常", "居家", "家庭", "吃饭", "睡觉", "起床", "上班", "下班"],
        "北京": ["北京", "北平", "京城", "首都", "京", "北二环", "北三环", "国贸", "三里屯", "望京", "海淀", "朝阳"],
        "美食": ["美食", "吃饭", "餐厅", "菜", "饭", "吃", "味道", "好吃", "难吃", "早餐", "午餐", "晚餐", "厨房", "做饭"],
        "天气": ["天气", "气温", "下雨", "晴天", "阴天", "下雪", "刮风", "温度", "冷热", "太阳", "云"],
        "日常": ["日常", "平常", "平时", "今天", "明天", "昨天", "早上", "晚上"],
        "心情": ["心情", "开心", "难过", "高兴", "伤心", "激动", "平静", "焦虑", "紧张", "放松", "舒服", "难受"],
        "旅行": ["旅行", "旅游", "出门", "出发", "到达", "酒店", "景点", "游玩", "风景", "机场", "车站", "高铁", "飞机"],
        "学习": ["学习", "看书", "读书", "考试", "学校", "大学", "老师", "学生", "课程", "知识", "专业"],
        "工作": ["工作", "上班", "加班", "公司", "同事", "老板", "项目", "客户", "会议", "报告", "职场"],
        "健康": ["健康", "运动", "健身", "跑步", "生病", "医院", "医生", "身体", "锻炼"],
        "娱乐": ["电影", "电视剧", "综艺", "音乐", "游戏", "玩", "唱歌", "跳舞", "娱乐", "休闲"],
        "社交": ["朋友", "聚会", "聊天", "见面", "约会", "社交", "人际关系"],
    }

    import re
    cleaned_text = text.lower()
    tag_scores = {}

    for tag, keywords in tag_keywords.items():
        score = 0
        for keyword in keywords:
            count = len(re.findall(re.escape(keyword), cleaned_text))
            if count > 0:
                score += count * (len(keyword) / 2)
        if score > 0:
            tag_scores[tag] = score

    sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
    selected_tags = [tag for tag, score in sorted_tags[:max_tags]]

    if not selected_tags:
        selected_tags = ["日常"]

    return selected_tags


async def batch_update_segments(batch_size: int = 50):
    """批量更新语弹数据"""
    # 初始化数据库连接
    from shared.database.session import init_db, async_session_maker as session_maker
    await init_db()

    # 重新获取 session maker
    from shared.database import session
    async with session.async_session_maker() as db:
        # 获取所有语弹
        stmt = select(AudioSegment).where(AudioSegment.transcription.isnot(None))
        result = await db.execute(stmt)
        segments = result.scalars().all()

        total = len(segments)
        print(f"找到 {total} 条语弹需要更新")

        updated = 0
        for i, segment in enumerate(segments):
            try:
                # 分析情感
                emotion_result = await analyze_emotion(segment.transcription)
                emotion = emotion_result.get("emotion", "平静")

                # 提取标签
                tags = extract_tags_from_text(segment.transcription)

                # 更新数据
                segment.emotion = emotion
                segment.tags = tags

                updated += 1
                if (i + 1) % 10 == 0:
                    print(f"已处理 {i + 1}/{total} 条语弹...")

                # 每 batch_size 条提交一次
                if updated % batch_size == 0:
                    await db.commit()
                    print(f"已提交 {updated} 条更新")

            except Exception as e:
                print(f"处理语弹 {segment.id} 时出错: {e}")
                continue

        # 提交剩余更新
        await db.commit()
        print(f"\n更新完成！共更新 {updated} 条语弹")


if __name__ == "__main__":
    print("开始批量更新语弹数据...")
    asyncio.run(batch_update_segments())
