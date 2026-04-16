import asyncio
import json
from pathlib import Path
from shared.models.audio import AudioSegment, AudioSource
from config import settings
from shared.database.session import async_session_maker
from sqlalchemy import select

async def check():
    index_path = Path(settings.FAISS_INDEX_PATH)
    metadata_path = index_path.with_suffix(".json")
    
    print("FAISS Index Check")
    print("=" * 60)
    
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    segment_ids = metadata.get("segment_ids", [])
    print(f"Segments in index: {len(segment_ids)}")
    
    async with async_session_maker() as db:
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

asyncio.run(check())
