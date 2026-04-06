#!/usr/bin/env python3
"""
本地音频文件夹自动监控入库脚本

功能：
1. 监控指定文件夹，自动检测新添加的音频文件
2. 支持 .mp3, .m4a, .wav, .flac, .ogg, .aac 格式
3. 自动处理：ASR识别 → 智能分割 → 语弹入库
4. 防重复处理：通过文件哈希避免重复入库
5. 处理完成后可选择：移动到完成目录 / 保留原文件 / 删除原文件

使用方法：
1. 直接运行（监控默认目录）：
   python -m scripts.auto_ingest

2. 监控指定目录：
   python -m scripts.auto_ingest /path/to/audio/folder

3. 完整选项：
   python -m scripts.auto_ingest /path/to/audio/folder
     --interval 30                # 每30秒检查一次（默认60秒）
     --preset-user preset-user-001   # 使用预设用户ID
     --on-complete move           # 完成后移动到 done/ 目录（可选：keep, delete）
     --max-concurrent 2           # 最多同时处理2个文件

Docker环境运行：
   docker-compose exec api python -m scripts.auto_ingest /app/data/audio_import
"""

import asyncio
import sys
import os
import logging
import argparse
from pathlib import Path
from datetime import datetime
import time
import uuid
import hashlib
from typing import Set, Dict, Optional
from dataclasses import dataclass, field

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.database.session import init_db, async_session_maker
from shared.models.audio import AudioSource
from shared.models.user import User
from services.audio_service import upload_audio, _process_audio_source_background
from config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/auto_ingest.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 支持的音频格式
SUPPORTED_EXTENSIONS = {'.mp3', '.m4a', '.wav', '.flac', '.ogg', '.aac'}


@dataclass
class ProcessingRecord:
    """处理记录"""
    file_path: Path
    file_hash: str
    status: str = "pending"  # pending, processing, completed, failed
    source_id: Optional[str] = None
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None


class AutoIngestManager:
    """自动入库管理器"""

    def __init__(
        self,
        watch_dir: Path,
        user_id: str = "preset-user-001",
        interval: int = 60,
        on_complete: str = "keep",  # keep, move, delete
        max_concurrent: int = 2
    ):
        self.watch_dir = watch_dir.resolve()
        self.user_id = user_id
        self.interval = interval
        self.on_complete = on_complete
        self.max_concurrent = max_concurrent

        self.processed_hashes: Set[str] = set()  # 已处理的文件哈希
        self.processing_files: Dict[Path, ProcessingRecord] = {}  # 正在处理的文件
        self.db: Optional[AsyncSession] = None

        # 确保目录存在
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        if on_complete == "move":
            self.done_dir = self.watch_dir / "done"
            self.done_dir.mkdir(exist_ok=True)
            self.failed_dir = self.watch_dir / "failed"
            self.failed_dir.mkdir(exist_ok=True)

        # 日志目录
        Path("logs").mkdir(exist_ok=True)

    async def initialize(self):
        """初始化数据库连接"""
        await init_db()
        logger.info(f"数据库连接已初始化")

        # 加载已处理的文件哈希
        await self._load_processed_hashes()
        logger.info(f"已加载 {len(self.processed_hashes)} 个已处理文件记录")

    async def _load_processed_hashes(self):
        """从数据库加载已处理的文件哈希"""
        async with async_session_maker() as db:
            # 获取所有已处理的音频源
            stmt = select(AudioSource).where(
                AudioSource.program_type == "auto_ingest"
            )
            result = await db.execute(stmt)
            sources = result.scalars().all()

            for source in sources:
                # 使用 original_filename 作为去重标识
                if source.original_filename:
                    file_hash = hashlib.md5(
                        source.original_filename.encode()
                    ).hexdigest()
                    self.processed_hashes.add(file_hash)

    def calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希（使用文件名+大小+修改时间）"""
        stat = file_path.stat()
        hash_content = f"{file_path.name}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.md5(hash_content.encode()).hexdigest()

    def scan_audio_files(self) -> list[Path]:
        """扫描音频文件"""
        audio_files = []

        for ext in SUPPORTED_EXTENSIONS:
            audio_files.extend(self.watch_dir.glob(f"*{ext}"))
            audio_files.extend(self.watch_dir.glob(f"*{ext.upper()}"))

        # 排除子目录中的文件
        audio_files = [
            f for f in audio_files
            if f.parent == self.watch_dir
        ]

        return sorted(audio_files, key=lambda p: p.stat().st_mtime)

    async def process_single_file(self, file_path: Path) -> bool:
        """处理单个音频文件"""
        record = ProcessingRecord(
            file_path=file_path,
            file_hash=self.calculate_file_hash(file_path)
        )

        # 检查是否已处理
        if record.file_hash in self.processed_hashes:
            logger.info(f"跳过已处理文件: {file_path.name}")
            return True

        # 检查是否正在处理
        if file_path in self.processing_files:
            logger.info(f"文件正在处理中: {file_path.name}")
            return False

        self.processing_files[file_path] = record
        record.status = "processing"

        try:
            logger.info(f"开始处理: {file_path.name}")

            async with async_session_maker() as db:
                # 获取用户
                stmt = select(User).where(User.id == self.user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    # 创建默认用户
                    user = User(
                        id=self.user_id,
                        nickname="AutoIngest",
                        is_admin=True
                    )
                    db.add(user)
                    await db.commit()
                    await db.refresh(user)

                # 复制文件到上传目录并创建记录
                import shutil
                import uuid
                from pathlib import Path

                upload_id = str(uuid.uuid4())
                upload_dir = Path("data/uploads") / upload_id
                upload_dir.mkdir(parents=True, exist_ok=True)

                target_path = upload_dir / file_path.name
                shutil.copy2(file_path, target_path)

                # 创建音频源记录
                from shared.models.audio import AudioSource
                import os

                file_size = target_path.stat().st_size
                file_format = file_path.suffix.lower().lstrip('.')

                source = AudioSource(
                    id=upload_id,
                    title=file_path.stem,
                    description=f"自动导入: {file_path.name}",
                    program_type="auto_ingest",
                    tags=[],
                    is_public=True,
                    original_filename=file_path.name,
                    file_size=file_size,
                    duration=0,  # 将在处理时计算
                    format=file_format if file_format else "mp3",
                    sample_rate=44100,
                    channels=2,
                    oss_key=f"audio/upload/{upload_id}/{file_path.name}",
                    oss_url=str(target_path),
                    processing_status="pending",
                )

                db.add(source)
                await db.commit()

                # 启动后台处理
                await _process_audio_source_background(source.id, user.id)

                record.source_id = source.id
                record.status = "completed"
                record.processed_at = datetime.now()

                self.processed_hashes.add(record.file_hash)

                logger.info(f"✅ 处理完成: {file_path.name} -> {source.id}")

                # 处理完成后的操作
                await self._handle_post_process(file_path, success=True)

                return True

        except Exception as e:
            record.status = "failed"
            record.error_message = str(e)
            logger.error(f"❌ 处理失败: {file_path.name} - {e}")

            await self._handle_post_process(file_path, success=False)
            return False

        finally:
            if file_path in self.processing_files:
                del self.processing_files[file_path]

    async def _handle_post_process(self, file_path: Path, success: bool):
        """处理完成后的文件操作"""
        if self.on_complete == "move":
            target_dir = self.done_dir if success else self.failed_dir
            target_path = target_dir / file_path.name

            # 如果目标已存在，添加时间戳
            if target_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                target_path = target_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"

            try:
                file_path.rename(target_path)
                logger.info(f"📁 文件已移动到: {target_path}")
            except Exception as e:
                logger.error(f"移动文件失败: {e}")

        elif self.on_complete == "delete" and success:
            try:
                file_path.unlink()
                logger.info(f"🗑️ 文件已删除: {file_path.name}")
            except Exception as e:
                logger.error(f"删除文件失败: {e}")

    async def run_once(self):
        """运行一次扫描和处理"""
        audio_files = self.scan_audio_files()

        if not audio_files:
            logger.debug("未发现新音频文件")
            return

        logger.info(f"发现 {len(audio_files)} 个音频文件")

        # 限制并发数
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_with_limit(file_path: Path):
            async with semaphore:
                return await self.process_single_file(file_path)

        # 并发处理
        tasks = [process_with_limit(f) for f in audio_files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计
        success_count = sum(1 for r in results if r is True)
        failed_count = sum(1 for r in results if r is False)
        error_count = sum(1 for r in results if isinstance(r, Exception))

        if success_count or failed_count or error_count:
            logger.info(
                f"📊 本次处理完成: 成功 {success_count}, 失败 {failed_count}, 错误 {error_count}"
            )

    async def run_forever(self):
        """持续运行监控"""
        logger.info(f"🚀 启动自动入库监控")
        logger.info(f"📁 监控目录: {self.watch_dir}")
        logger.info(f"⏱️ 检查间隔: {self.interval} 秒")
        logger.info(f"✅ 完成后操作: {self.on_complete}")
        logger.info(f"🔧 最大并发: {self.max_concurrent}")
        logger.info(f" Press Ctrl+C to stop\n")

        try:
            while True:
                await self.run_once()
                await asyncio.sleep(self.interval)

        except KeyboardInterrupt:
            logger.info("\n👋 收到停止信号，正在关闭...")


def main():
    parser = argparse.ArgumentParser(
        description="本地音频文件夹自动监控入库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 监控默认目录 (data/auto_import)
  python -m scripts.auto_ingest

  # 监控指定目录
  python -m scripts.auto_ingest /path/to/audio

  # Docker 环境
  docker-compose exec api python -m scripts.auto_ingest /app/data/audio_import

  # 每30秒检查，最多2个并发，完成后移动到 done/ 目录
  python -m scripts.auto_ingest ./my_audio --interval 30 --max-concurrent 2 --on-complete move
        """
    )

    parser.add_argument(
        "watch_dir",
        nargs="?",
        type=Path,
        default=Path("data/auto_import"),
        help="要监控的音频文件夹路径 (默认: data/auto_import)"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="检查间隔（秒），默认 60"
    )

    parser.add_argument(
        "--preset-user",
        default="preset-user-001",
        help="用于入库的预设用户ID，默认 preset-user-001"
    )

    parser.add_argument(
        "--on-complete",
        choices=["keep", "move", "delete"],
        default="keep",
        help="处理完成后操作: keep(保留), move(移到done目录), delete(删除)。默认 keep"
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=2,
        help="最大并发处理数，默认 2"
    )

    args = parser.parse_args()

    # 创建管理器
    manager = AutoIngestManager(
        watch_dir=args.watch_dir,
        user_id=args.preset_user,
        interval=args.interval,
        on_complete=args.on_complete,
        max_concurrent=args.max_concurrent
    )

    # 运行
    asyncio.run(run_manager(manager))


async def run_manager(manager: AutoIngestManager):
    """运行管理器"""
    await manager.initialize()
    await manager.run_forever()


if __name__ == "__main__":
    main()
