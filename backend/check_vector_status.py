#!/usr/bin/env python3
"""
检查音频片段向量状态
"""
import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from shared.models.audio import AudioSegment


async def check_vectors():
    # 使用容器内的MySQL连接
    engine = create_async_engine(
        'mysql+asyncmy://soundverse:password@mysql:3306/soundverse',
        echo=False
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 查询已审核的片段
        stmt = select(AudioSegment).where(AudioSegment.review_status == 'approved')
        result = await db.execute(stmt)
        segments = result.scalars().all()

        print(f'已审核片段总数: {len(segments)}')

        with_vector = 0
        without_vector = 0
        vector_dimensions = {}

        for seg in segments:
            if seg.vector is not None:
                with_vector += 1
                # 检查向量维度
                dim = seg.vector_dimension
                if dim:
                    vector_dimensions[dim] = vector_dimensions.get(dim, 0) + 1
                else:
                    vector_dimensions['unknown'] = vector_dimensions.get('unknown', 0) + 1
            else:
                without_vector += 1

        print(f'有向量的片段: {with_vector}')
        print(f'无向量的片段: {without_vector}')

        if vector_dimensions:
            print('向量维度分布:')
            for dim, count in vector_dimensions.items():
                print(f'  维度 {dim}: {count} 个片段')

        if with_vector > 0 and without_vector > 0:
            print('状态: 部分片段有向量，部分没有')
        elif with_vector == 0:
            print('状态: 所有片段都没有向量 - 需要生成向量')
        else:
            print('状态: 所有片段都有向量 - 可以直接同步到DashVector')


if __name__ == '__main__':
    asyncio.run(check_vectors())