#!/usr/bin/env python3
"""
更新OSS URL脚本 - 将旧域名替换为新域名

此脚本更新数据库中所有音频片段和音频源的OSS URL，将：
- https://soundverse-audio.oss-cn-hangzhou.aliyuncs.com
- https://ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com
替换为：
- https://ai-sun.vbegin.com.cn

保留路径部分不变。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

async def update_oss_urls():
    """更新OSS URL"""
    # 使用localhost连接MySQL
    DATABASE_URL = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        try:
            print("=== 更新音频源OSS URL ===")

            # 更新AudioSource表中的OSS URL
            update_sources_sql = text("""
                UPDATE audio_sources
                SET oss_url = REPLACE(
                    REPLACE(
                        oss_url,
                        'https://soundverse-audio.oss-cn-hangzhou.aliyuncs.com',
                        'https://ai-sun.vbegin.com.cn'
                    ),
                    'https://ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com',
                    'https://ai-sun.vbegin.com.cn'
                )
                WHERE oss_url LIKE '%soundverse-audio.oss-cn-hangzhou.aliyuncs.com%'
                   OR oss_url LIKE '%ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com%'
            """)

            result = await db.execute(update_sources_sql)
            await db.commit()
            print(f"更新了 {result.rowcount} 个音频源记录")

            # 显示更新后的音频源
            select_sources_sql = text("SELECT id, title, oss_url FROM audio_sources")
            sources_result = await db.execute(select_sources_sql)
            sources = sources_result.fetchall()

            for source in sources:
                print(f"音频源: {source[1]} ({source[0]})")
                print(f"  URL: {source[2]}")

            print("\n=== 更新音频片段OSS URL ===")

            # 更新AudioSegment表中的OSS URL
            update_segments_sql = text("""
                UPDATE audio_segments
                SET oss_url = REPLACE(
                    REPLACE(
                        oss_url,
                        'https://soundverse-audio.oss-cn-hangzhou.aliyuncs.com',
                        'https://ai-sun.vbegin.com.cn'
                    ),
                    'https://ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com',
                    'https://ai-sun.vbegin.com.cn'
                )
                WHERE oss_url LIKE '%soundverse-audio.oss-cn-hangzhou.aliyuncs.com%'
                   OR oss_url LIKE '%ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com%'
            """)

            result = await db.execute(update_segments_sql)
            await db.commit()
            print(f"更新了 {result.rowcount} 个音频片段记录")

            # 显示更新后的片段
            select_segments_sql = text("SELECT id, transcription, oss_url FROM audio_segments LIMIT 10")
            segments_result = await db.execute(select_segments_sql)
            segments = segments_result.fetchall()

            for segment in segments:
                print(f"片段ID: {segment[0]}")
                print(f"  转录: {segment[1][:50] if segment[1] else '无'}")
                print(f"  URL: {segment[2]}")

            print("\n=== 更新完成 ===")

        except Exception as e:
            await db.rollback()
            print(f"更新失败: {str(e)}")
            raise

async def main():
    """主函数"""
    print("开始更新OSS URL...")
    print("将旧域名替换为新域名: https://ai-sun.vbegin.com.cn")
    print()

    try:
        await update_oss_urls()
        print("OSS URL更新成功!")
    except Exception as e:
        print(f"OSS URL更新失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())