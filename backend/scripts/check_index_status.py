#!/usr/bin/env python3
"""
Check FAISS index status - see which segments are indexed and from which programs
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

    # Ensure we're using async driver
    if "mysql+aiomysql" in db_url:
        db_url = db_url.replace("mysql+aiomysql://", "mysql+asyncmy://")
    elif "mysql://" in db_url and "asyncmy" not in db_url:
        db_url = db_url.replace("mysql://", "mysql+asyncmy://")

    # Replace localhost with mysql for Docker environment
    if "localhost" in db_url:
        db_url = db_url.replace("localhost", "mysql")
    elif "127.0.0.1" in db_url:
        db_url = db_url.replace("127.0.0.1", "mysql")

    print(f"Using database URL: {db_url[:50]}...")
    engine = create_async_engine(db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session


async def check_faiss_index():
    """Check FAISS index status"""
    index_path = Path(settings.FAISS_INDEX_PATH)
    metadata_path = index_path.with_suffix('.json')

    print("=" * 80)
    print("FAISS Index Status Check")
    print("=" * 80)

    if not metadata_path.exists():
        print(f"ERROR: Metadata file not found: {metadata_path}")
        return

    # Load metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    segment_ids = metadata.get('segment_ids', [])
    print(f"\n[Stats]")
    print(f"   - Segments in index: {len(segment_ids)}")
    print(f"   - Vector dimension: {metadata.get('vector_dimension', 'N/A')}")

    # Get database session
    async_session = await get_db_session()
    async with async_session() as db:
        # Query all indexed segments
        stmt = select(AudioSegment, AudioSource).join(
            AudioSource, AudioSegment.source_id == AudioSource.id
        ).where(AudioSegment.id.in_(segment_ids))

        result = await db.execute(stmt)
        segments = result.all()

        print(f"\n[Indexed Segments]")
        print(f"   - Found in database: {len(segments)} segments")

        # Group by source
        source_stats = {}
        indexed_segments = []

        for segment, source in segments:
            source_id = source.id
            source_title = source.title or "Unknown"

            if source_id not in source_stats:
                source_stats[source_id] = {
                    'title': source_title,
                    'count': 0,
                    'segments': []
                }

            source_stats[source_id]['count'] += 1
            source_stats[source_id]['segments'].append({
                'id': segment.id,
                'transcription': segment.transcription[:80] if segment.transcription else "N/A"
            })
            indexed_segments.append(segment.id)

        print(f"\n[By Program]")
        for source_id, info in source_stats.items():
            print(f"\n   Program: {info['title']} ({source_id[:8]}...)")
            print(f"   - Indexed segments: {info['count']}")

        # Check which IDs in index are not in database
        not_in_db = set(segment_ids) - set(indexed_segments)
        if not_in_db:
            print(f"\nWARNING: {len(not_in_db)} indexed IDs not found in database")

        # Query all approved segments in database
        stmt_all = select(AudioSegment, AudioSource).join(
            AudioSource, AudioSegment.source_id == AudioSource.id
        ).where(AudioSegment.review_status == 'approved')

        result_all = await db.execute(stmt_all)
        all_segments = result_all.all()

        print(f"\n[All Approved Segments in Database]")
        all_source_stats = {}
        not_indexed = []

        for segment, source in all_segments:
            source_id = source.id
            source_title = source.title or "Unknown"

            if source_id not in all_source_stats:
                all_source_stats[source_id] = {
                    'title': source_title,
                    'count': 0,
                    'not_indexed': []
                }

            all_source_stats[source_id]['count'] += 1

            if segment.id not in segment_ids:
                all_source_stats[source_id]['not_indexed'].append({
                    'id': segment.id,
                    'transcription': segment.transcription[:80] if segment.transcription else "N/A"
                })
                not_indexed.append(segment.id)

        for source_id, info in all_source_stats.items():
            print(f"\n   Program: {info['title']}")
            print(f"   - Total: {info['count']}")
            print(f"   - Indexed: {info['count'] - len(info['not_indexed'])}")
            print(f"   - Not indexed: {len(info['not_indexed'])}")

        print(f"\n[Summary]")
        print(f"   Total {len(not_indexed)} segments not indexed to FAISS")

        # Check if not indexed segments have vector fields
        print(f"\n[Checking vector fields for not-indexed segments...]")
        sample_not_indexed = not_indexed[:5] if not_indexed else []
        for seg_id in sample_not_indexed:
            stmt = select(AudioSegment).where(AudioSegment.id == seg_id)
            result = await db.execute(stmt)
            seg = result.scalar_one_or_none()
            if seg:
                has_vector = "YES" if seg.vector else "NO"
                print(f"   {seg_id[:8]}...: vector={has_vector}, dim={seg.vector_dimension}")


if __name__ == "__main__":
    asyncio.run(check_faiss_index())
