#!/usr/bin/env python3
"""
Check FAISS index status inside Docker container
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Mock audio_processing_service module to avoid pyaudioop import
import sys
sys.modules['services.audio_processing_service'] = type(sys)('audio_processing_service')
sys.modules['services.audio_processing_service'].audio_processing_service = object()

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from shared.models.audio import AudioSegment, AudioSource
from config import settings


async def get_db_session():
    """Create database session"""
    db_url = settings.DATABASE_URL

    # In Docker, replace localhost with mysql service name
    if "localhost" in db_url:
        db_url = db_url.replace("localhost", "mysql")
    elif "127.0.0.1" in db_url:
        db_url = db_url.replace("127.0.0.1", "mysql")

    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session


async def check():
    index_path = Path(settings.FAISS_INDEX_PATH)
    metadata_path = index_path.with_suffix(".json")

    print("FAISS Index Check")
    print("=" * 60)

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    segment_ids = metadata.get("segment_ids", [])
    print(f"Segments in index: {len(segment_ids)}")

    async_session = await get_db_session()
    async with async_session() as db:
        # Query indexed segments
        stmt = select(AudioSegment, AudioSource).join(
            AudioSource, AudioSegment.source_id == AudioSource.id
        ).where(AudioSegment.id.in_(segment_ids))

        result = await db.execute(stmt)
        segments = result.all()

        print(f"Found in DB: {len(segments)}")

        # Group by source
        source_stats = {}
        for seg, src in segments:
            if src.id not in source_stats:
                source_stats[src.id] = {"title": src.title, "count": 0}
            source_stats[src.id]["count"] += 1

        print("\nIndexed by Program:")
        for sid, info in source_stats.items():
            print(f"  {info['title']}: {info['count']}")

        # Query all approved
        stmt_all = select(AudioSegment, AudioSource).join(
            AudioSource, AudioSegment.source_id == AudioSource.id
        ).where(AudioSegment.review_status == "approved")

        result_all = await db.execute(stmt_all)
        all_segs = result_all.all()

        print(f"\nAll approved in DB: {len(all_segs)}")

        # Group by source
        all_stats = {}
        for seg, src in all_segs:
            if src.id not in all_stats:
                all_stats[src.id] = {"title": src.title, "total": 0, "indexed": 0}
            all_stats[src.id]["total"] += 1
            if seg.id in segment_ids:
                all_stats[src.id]["indexed"] += 1

        print("\nAll Programs:")
        for sid, info in all_stats.items():
            not_idx = info["total"] - info["indexed"]
            print(f"  {info['title']}: {info['indexed']}/{info['total']} indexed, {not_idx} not indexed")


if __name__ == "__main__":
    asyncio.run(check())
