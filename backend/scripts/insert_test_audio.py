#!/usr/bin/env python3
"""
插入测试音频片段到数据库
"""
import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from shared.models.audio import AudioSource, AudioSegment
from shared.models.user import User
from shared.models.chat import ChatMessage  # 确保关系解析

async def insert_test_data():
    """插入测试数据"""
    # 使用开发数据库配置
    DATABASE_URL = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("连接数据库...")

        # 检查是否有测试用户
        stmt = select(User).limit(1)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            print("未找到用户，创建测试用户...")
            user = User(
                id=str(uuid.uuid4()),
                wechat_openid=f"test_openid_{str(uuid.uuid4())[:8]}",
                nickname="测试用户",
                avatar_url="https://example.com/avatar.jpg",
                is_active=True,
                is_premium=False,
                is_admin=False,
                daily_chat_count=0,
                daily_generate_count=0,
                total_chat_count=0,
                total_generate_count=0,
                preferred_voice="default",
                preferred_language="zh-CN",
                notification_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"创建用户: {user.id}")

        # 检查是否有音频源
        stmt = select(AudioSource).limit(1)
        result = await db.execute(stmt)
        source = result.scalar_one_or_none()

        if not source:
            print("创建测试音频源...")
            source = AudioSource(
                id=str(uuid.uuid4()),
                title="测试广播节目",
                description="这是一个测试广播节目，用于开发测试",
                program_type="news",
                episode_number="001",
                broadcast_date=datetime.utcnow(),
                original_filename="test_radio.mp3",
                file_size=1024000,
                duration=300.0,
                format="mp3",
                sample_rate=16000,
                channels=1,
                oss_key="audio/test_radio.mp3",
                oss_url="https://ai-sun.vbegin.com.cn/audio/test_radio.mp3",
                processing_status="completed",
                processing_progress=1.0,
                copyright_holder="测试电台",
                license_type="test",
                is_public=True,
                tags=["新闻", "测试", "广播"],
                extra_metadata={"creator": "dev"},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(source)
            await db.commit()
            await db.refresh(source)
            print(f"创建音频源: {source.id}")

        # 插入测试音频片段
        test_segments = [
            {
                "transcription": "现在是北京时间八点整",
                "start_time": 0.0,
                "end_time": 5.0,
                "duration": 5.0,
            },
            {
                "transcription": "欢迎收听中央人民广播电台新闻广播",
                "start_time": 5.0,
                "end_time": 10.0,
                "duration": 5.0,
            },
            {
                "transcription": "今天的主要新闻有：国家领导人出席重要会议",
                "start_time": 10.0,
                "end_time": 15.0,
                "duration": 5.0,
            },
            {
                "transcription": "天气预报：今天白天晴转多云，气温20到25度",
                "start_time": 15.0,
                "end_time": 20.0,
                "duration": 5.0,
            },
            {
                "transcription": "接下来是体育新闻：中国女排取得胜利",
                "start_time": 20.0,
                "end_time": 25.0,
                "duration": 5.0,
            },
        ]

        inserted_count = 0
        for i, seg_data in enumerate(test_segments):
            # 检查是否已存在相同转录的片段
            stmt = select(AudioSegment).where(
                AudioSegment.transcription == seg_data["transcription"]
            ).limit(1)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                print(f"片段已存在: {seg_data['transcription'][:30]}...")
                continue

            segment = AudioSegment(
                id=str(uuid.uuid4()),
                source_id=source.id,
                user_id=user.id,
                start_time=seg_data["start_time"],
                end_time=seg_data["end_time"],
                duration=seg_data["duration"],
                transcription=seg_data["transcription"],
                language="zh-CN",
                speaker="播音员",
                emotion="neutral",
                sentiment_score=0.0,
                vector=None,
                vector_dimension=None,
                oss_key=f"audio/segment_{i}.mp3",
                oss_url=f"https://ai-sun.vbegin.com.cn/audio/segment_{i}.mp3",
                play_count=0,
                favorite_count=0,
                share_count=0,
                tags=["测试"],
                categories=["新闻"],
                keywords=["测试", "新闻"],
                review_status="approved",
                reviewer_id=user.id,
                review_comment="自动审核通过",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(segment)
            inserted_count += 1
            print(f"创建片段: {seg_data['transcription'][:30]}...")

        await db.commit()
        print(f"成功插入 {inserted_count} 个测试音频片段")

        # 验证插入的片段
        stmt = select(AudioSegment).where(AudioSegment.review_status == "approved")
        result = await db.execute(stmt)
        segments = result.scalars().all()
        print(f"数据库中已审核通过的片段总数: {len(segments)}")
        for seg in segments[:5]:
            print(f"  - {seg.transcription[:50]}...")

async def main():
    """主函数"""
    try:
        await insert_test_data()
    except Exception as e:
        print(f"插入测试数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))