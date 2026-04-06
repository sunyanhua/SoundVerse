#!/usr/bin/env python3
"""简化版自动入库脚本 - 用于调试"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, '/app')

from shared.database.session import init_db, async_session_maker
from shared.models.audio import AudioSource
from shared.models.user import User
from sqlalchemy import select
import shutil
import uuid

SUPPORTED_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac'}

async def main():
    print("=" * 50)
    print("简化版自动入库测试")
    print("=" * 50)

    # 初始化数据库
    await init_db()
    print("✅ 数据库已初始化")

    watch_dir = Path('/app/data/auto_import')
    print(f"📁 监控目录: {watch_dir}")
    print(f"   存在: {watch_dir.exists()}")

    # 扫描文件
    audio_files = []
    for ext in SUPPORTED_EXTENSIONS:
        audio_files.extend(watch_dir.glob(f'*{ext}'))
        audio_files.extend(watch_dir.glob(f'*{ext.upper()}'))
    audio_files = [f for f in audio_files if f.parent == watch_dir]

    print(f"\n🎵 发现 {len(audio_files)} 个音频文件:")
    for f in audio_files:
        print(f"   - {f.name}")

    if not audio_files:
        print("⚠️ 没有音频文件需要处理")
        return

    # 处理第一个文件
    file_path = audio_files[0]
    print(f"\n🚀 处理文件: {file_path.name}")

    async with async_session_maker() as db:
        # 获取或创建用户
        stmt = select(User).where(User.id == 'preset-user-001')
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            user = User(id='preset-user-001', nickname='AutoIngest', is_admin=True)
            db.add(user)
            await db.commit()
            print("✅ 创建用户")
        else:
            print("✅ 找到用户")

        # 复制文件到上传目录
        upload_id = str(uuid.uuid4())
        upload_dir = Path('/app/data/uploads') / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        target_path = upload_dir / file_path.name
        shutil.copy2(file_path, target_path)
        print(f"✅ 复制文件到: {target_path}")

        # 创建音频源记录
        source = AudioSource(
            id=upload_id,
            title=file_path.stem,
            description=f"自动导入: {file_path.name}",
            program_type="auto_ingest",
            tags=[],
            is_public=True,
            original_filename=file_path.name,
            file_size=target_path.stat().st_size,
            duration=0,
            format=file_path.suffix.lower().lstrip('.') or 'wav',
            sample_rate=44100,
            channels=2,
            oss_key=f"audio/upload/{upload_id}/{file_path.name}",
            oss_url=str(target_path),
            processing_status="pending",
        )

        db.add(source)
        await db.commit()
        print(f"✅ 创建音频源记录: {upload_id}")

        # 启动后台处理
        from services.audio_service import _process_audio_source_background
        asyncio.create_task(_process_audio_source_background(source.id, user.id))
        print(f"✅ 启动后台处理任务")

        # 移动原文件到 done
        done_dir = watch_dir / 'done'
        done_dir.mkdir(exist_ok=True)
        done_path = done_dir / file_path.name
        file_path.rename(done_path)
        print(f"✅ 移动原文件到: {done_path}")

    print("\n✨ 处理完成!")

if __name__ == '__main__':
    asyncio.run(main())
