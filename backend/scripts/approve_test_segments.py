#!/usr/bin/env python3
"""
批准测试音频片段 - 将所有测试片段的review_status设置为approved
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

async def approve_test_segments():
    """批准测试音频片段"""
    # 使用localhost连接MySQL
    DATABASE_URL = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        try:
            print("=== 更新音频片段审核状态 ===")

            # 将所有片段的review_status更新为approved
            update_sql = text("""
                UPDATE audio_segments
                SET review_status = 'approved',
                    updated_at = NOW()
                WHERE review_status = 'pending'
            """)

            result = await db.execute(update_sql)
            await db.commit()
            print(f"更新了 {result.rowcount} 个音频片段为approved状态")

            # 验证更新结果
            check_sql = text("""
                SELECT review_status, COUNT(*) as count
                FROM audio_segments
                GROUP BY review_status
            """)
            check_result = await db.execute(check_sql)
            status_counts = check_result.fetchall()

            print("\n=== 更新后状态分布 ===")
            for status, count in status_counts:
                print(f"  {status}: {count}")

            # 显示一些approved片段
            sample_sql = text("""
                SELECT id, transcription, oss_url
                FROM audio_segments
                WHERE review_status = 'approved'
                LIMIT 5
            """)
            sample_result = await db.execute(sample_sql)
            samples = sample_result.fetchall()

            print("\n=== approved片段示例 ===")
            for i, sample in enumerate(samples):
                print(f"{i+1}. ID: {sample[0][:8]}...")
                if sample[1]:
                    print(f"   转录: {sample[1][:80]}")
                else:
                    print(f"   转录: 无")
                if sample[2]:
                    print(f"   URL: {sample[2][:80]}")
                print()

            print("=== 更新完成 ===")

        except Exception as e:
            await db.rollback()
            print(f"更新失败: {str(e)}")
            raise

async def main():
    """主函数"""
    print("开始更新音频片段审核状态...")
    print("将所有pending状态的片段更新为approved")
    print()

    try:
        await approve_test_segments()
        print("\n音频片段审核状态更新成功!")
    except Exception as e:
        print(f"更新失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())