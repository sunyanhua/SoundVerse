"""
音频服务
"""
import logging
import uuid
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.audio import AudioSource, AudioSegment, FavoriteSegment
from shared.models.user import User
from shared.schemas.audio import (
    AudioUploadRequest,
    AudioUploadResponse,
    AudioProcessingStatus,
    AudioSearchRequest,
    AudioSearchResponse,
    AudioSearchResult,
    AudioSegmentResponse,
    FavoriteSegmentCreate,
    FavoriteSegmentResponse,
)
from config import settings
# audio_processing_service 导入移到需要使用它的函数内部，避免pydub依赖问题

logger = logging.getLogger(__name__)


def _fix_audio_url_for_dev(audio_url: Optional[str]) -> Optional[str]:
    """
    开发环境下修复音频URL，确保可访问
    """
    if not audio_url:
        return audio_url

    # 开发环境下使用测试音频文件
    if settings.ENVIRONMENT == "development":
        # 检查URL是否包含无法访问的旧测试域名
        # 只替换旧的无法访问的域名，保留可访问的OSS URL
        old_test_domains = [
            # "ai-sun.vbegin.com.cn",  # 旧格式，无法访问
        ]

        # 新的OSS格式可以访问，不需要替换
        # ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com 是真实可访问的OSS URL

        for domain in old_test_domains:
            if domain in audio_url:
                # 使用一个公开可访问的测试音频文件
                # 这是一个公开的测试MP3文件，可以跨域访问
                test_audio_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
                logger.info(f"开发环境：替换旧的无法访问音频URL {audio_url} -> {test_audio_url}")
                return test_audio_url

        # 如果URL包含新的OSS格式，记录但不替换
        if "ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com" in audio_url:
            logger.debug(f"开发环境：保留可访问的OSS URL: {audio_url}")
        elif "oss-cn-beijing.aliyuncs.com" in audio_url:
            logger.debug(f"开发环境：保留OSS URL: {audio_url}")

    return audio_url


async def upload_audio(
    db: AsyncSession,
    user: User,
    audio_file: Any,
    request: AudioUploadRequest,
) -> AudioUploadResponse:
    """
    上传音频文件
    """
    # 生成上传ID
    upload_id = str(uuid.uuid4())

    # 在实际实现中，这里应该：
    # 1. 将文件上传到OSS
    # 2. 创建音频源记录
    # 3. 启动异步处理任务

    # 模拟返回上传响应
    response = AudioUploadResponse(
        upload_id=upload_id,
        oss_policy={
            "accessid": "test-access-id",
            "policy": "test-policy",
            "signature": "test-signature",
            "dir": "audio/upload/",
            "host": "https://oss.example.com",
            "expire": 3600,
        },
        oss_signature="test-signature",
        oss_key=f"audio/upload/{upload_id}/{audio_file.filename}",
        oss_host="https://oss.example.com",
        callback_url=f"{settings.HOST}/api/v1/audio/upload/callback",
    )

    # 创建音频源记录（异步）
    source = AudioSource(
        title=request.title,
        description=request.description,
        program_type=request.program_type,
        tags=request.tags,
        is_public=request.is_public,
        original_filename=audio_file.filename,
        file_size=0,  # 实际应从文件获取
        duration=0,  # 实际应从文件获取
        format="mp3",  # 实际应从文件获取
        sample_rate=44100,  # 默认值
        channels=2,  # 默认值
        oss_key=response.oss_key,
        oss_url=f"{response.oss_host}/{response.oss_key}",
        processing_status="pending",
    )

    db.add(source)
    await db.commit()

    logger.info(f"用户 {user.id} 上传音频: {upload_id}")

    # 启动后台处理任务（模拟）
    asyncio.create_task(_process_audio_source_background(source.id, user.id))

    return response


async def get_audio_processing_status(
    db: AsyncSession,
    processing_id: str,
    user_id: str,
) -> AudioProcessingStatus:
    """
    获取音频处理状态
    """
    # 查找音频源
    stmt = select(AudioSource).where(AudioSource.id == processing_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        raise ValueError("处理任务不存在")

    # 检查权限（用户只能查看自己的音频或公开音频）
    # 这里简化处理

    return AudioProcessingStatus(
        processing_id=processing_id,
        status=source.processing_status,
        progress=source.processing_progress,
        error_message=source.error_message,
        result={
            "source_id": source.id,
            "segments_count": len(source.segments) if source.segments else 0,
        } if source.processing_status == "completed" else None,
    )


async def search_audio_segments(
    db: AsyncSession,
    request: AudioSearchRequest,
    user_id: str,
) -> AudioSearchResponse:
    """
    搜索音频片段
    """
    from services.search_service import search_audio_segments_by_text
    from sqlalchemy import select, and_
    from shared.models.audio import AudioSegment, AudioSource

    # 使用向量搜索查找相似的片段
    search_results = []
    similarity_threshold = settings.SIMILARITY_THRESHOLD  # 阈值变量

    try:
        search_results = await search_audio_segments_by_text(
            query_text=request.query,
            top_k=request.limit,
            similarity_threshold=similarity_threshold,
        )
    except Exception as e:
        logger.warning(f"向量搜索失败，禁止使用文本匹配回退: {str(e)}")
        # 向量搜索失败，直接返回空，触发LLM文字回复
        search_results = []

    # 向量搜索无结果，禁止使用文本匹配回退，直接返回空触发LLM文字回复
    if not search_results:
        logger.info(f"向量搜索无结果，禁止文本匹配回退，触发LLM文字回复: '{request.query}'")

    # 获取片段ID列表
    segment_ids = [segment_id for segment_id, similarity in search_results]

    # 从数据库获取完整的片段信息
    stmt = select(AudioSegment).options(
        selectinload(AudioSegment.source)
    ).where(
        AudioSegment.review_status == "approved",
        AudioSegment.id.in_(segment_ids),
    )

    # 应用时长过滤
    if request.min_duration is not None:
        stmt = stmt.where(AudioSegment.duration >= request.min_duration)
    if request.max_duration is not None:
        stmt = stmt.where(AudioSegment.duration <= request.max_duration)

    # 应用语言过滤
    if request.language:
        stmt = stmt.where(AudioSegment.language == request.language)

    result = await db.execute(stmt)
    segments = result.scalars().all()

    # 创建ID到片段的映射
    segment_map = {seg.id: seg for seg in segments}

    # 创建ID到相似度分数的映射
    similarity_map = {segment_id: similarity for segment_id, similarity in search_results}

    # 转换为响应格式，按相似度排序
    results = []
    for segment_id, similarity in search_results:
        segment = segment_map.get(segment_id)
        if not segment:
            continue

        # 检查节目类型过滤
        if request.program_types and segment.source:
            if segment.source.program_type not in request.program_types:
                continue

        # 修复OSS URL，将旧域名替换为新域名
        audio_url = segment.oss_url
        if audio_url and "oss-cn-hangzhou.aliyuncs.com" in audio_url:
            # 替换旧域名为新域名
            audio_url = audio_url.replace(
                "https://soundverse-audio.oss-cn-hangzhou.aliyuncs.com",
                "https://ai-sun.vbegin.com.cn"
            )

        # 开发环境下修复音频URL
        audio_url = _fix_audio_url_for_dev(audio_url)

        # 创建segment字典副本，移除oss_url以避免重复参数
        segment_dict = segment.__dict__.copy()
        if 'oss_url' in segment_dict:
            del segment_dict['oss_url']

        results.append(AudioSearchResult(
            segment=AudioSegmentResponse(
                **segment_dict,
                is_favorite=False,  # 需要查询用户收藏状态
                source_title=segment.source.title if segment.source else None,
                oss_url=audio_url,  # 使用修复后的URL
            ),
            similarity_score=similarity,
            relevance_explanation=f"与查询'{request.query}'语义相似，相似度{similarity:.2f}",
        ))

    return AudioSearchResponse(
        query=request.query,
        results=results,
        total_count=len(results),
        processing_time_ms=150.5,
    )


async def get_audio_segment(
    db: AsyncSession,
    segment_id: str,
    user_id: str,
) -> AudioSegmentResponse:
    """
    获取音频片段详情
    """
    stmt = select(AudioSegment).options(
        selectinload(AudioSegment.source)
    ).where(AudioSegment.id == segment_id)
    result = await db.execute(stmt)
    segment = result.scalar_one_or_none()

    if not segment:
        raise ValueError("音频片段不存在")

    # 检查权限
    # 如果user_id为None（管理后台请求），允许访问所有片段
    if user_id is not None and segment.review_status != "approved" and segment.user_id != user_id:
        raise ValueError("没有权限访问此音频片段")

    # 检查用户是否收藏
    fav_stmt = select(FavoriteSegment).where(
        FavoriteSegment.user_id == user_id,
        FavoriteSegment.segment_id == segment_id,
    )
    fav_result = await db.execute(fav_stmt)
    is_favorite = fav_result.scalar_one_or_none() is not None

    # 创建segment字典副本
    segment_dict = segment.__dict__.copy()

    # 获取并修复音频URL
    audio_url = segment_dict.get('oss_url')
    audio_url = _fix_audio_url_for_dev(audio_url)

    # 移除oss_url以避免重复参数
    if 'oss_url' in segment_dict:
        del segment_dict['oss_url']

    return AudioSegmentResponse(
        **segment_dict,
        is_favorite=is_favorite,
        source_title=segment.source.title if segment.source else None,
        oss_url=audio_url,
    )


async def favorite_audio_segment(
    db: AsyncSession,
    user_id: str,
    segment_id: str,
) -> FavoriteSegmentResponse:
    """
    收藏音频片段
    """
    # 检查片段是否存在
    stmt = select(AudioSegment).where(
        AudioSegment.id == segment_id,
        AudioSegment.review_status == "approved",
    )
    result = await db.execute(stmt)
    segment = result.scalar_one_or_none()

    if not segment:
        raise ValueError("音频片段不存在或未审核通过")

    # 检查是否已收藏
    fav_stmt = select(FavoriteSegment).where(
        FavoriteSegment.user_id == user_id,
        FavoriteSegment.segment_id == segment_id,
    )
    fav_result = await db.execute(fav_stmt)
    existing_fav = fav_result.scalar_one_or_none()

    if existing_fav:
        raise ValueError("已经收藏过此音频片段")

    # 创建收藏记录
    favorite = FavoriteSegment(
        user_id=user_id,
        segment_id=segment_id,
    )

    db.add(favorite)

    # 更新片段收藏计数
    segment.increment_favorite_count()

    await db.commit()

    return FavoriteSegmentResponse(
        id=favorite.id,
        user_id=user_id,
        segment=await get_audio_segment(db, segment_id, user_id),
        created_at=favorite.created_at,
    )


async def get_user_favorites(
    db: AsyncSession,
    user_id: str,
    limit: int,
    offset: int,
) -> List[FavoriteSegmentResponse]:
    """
    获取用户收藏的音频片段
    """
    stmt = select(FavoriteSegment).where(
        FavoriteSegment.user_id == user_id
    ).order_by(
        FavoriteSegment.created_at.desc()
    ).limit(limit).offset(offset)

    result = await db.execute(stmt)
    favorites = result.scalars().all()

    responses = []
    for fav in favorites:
        try:
            segment_response = await get_audio_segment(db, fav.segment_id, user_id)
            responses.append(FavoriteSegmentResponse(
                id=fav.id,
                user_id=user_id,
                segment=segment_response,
                created_at=fav.created_at,
            ))
        except ValueError:
            # 片段可能已被删除
            continue

    return responses


async def delete_audio_source(
    db: AsyncSession,
    source_id: str,
    user: User,
) -> bool:
    """
    删除音频源
    """
    stmt = select(AudioSource).where(AudioSource.id == source_id)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()

    if not source:
        return False

    # 检查权限：管理员或上传者
    # 这里简化处理：只允许管理员删除
    if not user.is_admin:
        return False

    # 在实际实现中，这里应该：
    # 1. 删除OSS上的文件
    # 2. 删除数据库记录
    # 3. 删除相关索引

    # 这里只标记为删除
    source.processing_status = "deleted"
    await db.commit()

    return True


async def get_recommended_audios(
    db: AsyncSession,
    user_id: Optional[str] = None,
    limit: int = 10,
) -> List[AudioSegmentResponse]:
    """
    获取推荐音频片段
    """
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from shared.models.audio import AudioSegment
    from shared.schemas.audio import AudioSegmentResponse

    # 随机获取已审核通过的音频片段
    stmt = select(AudioSegment).options(
        selectinload(AudioSegment.source)
    ).where(
        AudioSegment.review_status == "approved"
    ).order_by(
        func.random()
    ).limit(limit)

    result = await db.execute(stmt)
    segments = result.scalars().all()

    responses = []
    for segment in segments:
        # 创建segment.__dict__副本并移除oss_url键
        segment_dict = segment.__dict__.copy()
        segment_dict.pop('oss_url', None)

        # 获取source_title
        source_title = segment.source.title if segment.source else None

        # 修复音频URL
        audio_url = _fix_audio_url_for_dev(segment.oss_url)

        response = AudioSegmentResponse(
            **segment_dict,
            source_title=source_title,
            oss_url=audio_url,
            is_favorite=False,  # 暂时设置为False，需要时可以查询收藏状态
        )
        responses.append(response)

    return responses


async def get_audio_segments_paginated(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    query: Optional[str] = None,
    review_status: Optional[str] = None,
    source_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
) -> dict:
    """
    获取分页的音频片段列表（用于管理界面）
    """
    from sqlalchemy import select, func, and_, or_
    from sqlalchemy.orm import selectinload
    from shared.models.audio import AudioSegment, AudioSource
    from shared.schemas.audio import AudioSegmentResponse

    # 构建查询
    stmt = select(AudioSegment).options(
        selectinload(AudioSegment.source)
    )

    # 应用过滤条件
    conditions = []

    # 审核状态过滤
    if review_status:
        conditions.append(AudioSegment.review_status == review_status)

    # 日期范围过滤
    if start_date:
        conditions.append(AudioSegment.created_at >= start_date)
    if end_date:
        conditions.append(AudioSegment.created_at <= end_date)

    # 文本查询（转录文本或ID）
    if query:
        query_lower = query.lower()
        # 尝试将query解析为数字ID
        try:
            segment_id = int(query)
            conditions.append(AudioSegment.id == segment_id)
        except ValueError:
            # 如果不是数字，则在转录文本中搜索
            conditions.append(AudioSegment.transcription.ilike(f"%{query}%"))

    # 音频源名称过滤
    if source_name:
        # 需要在子查询中过滤source名称
        stmt = stmt.join(AudioSource)
        conditions.append(
            or_(
                AudioSource.title.ilike(f"%{source_name}%"),
                AudioSource.program_type.ilike(f"%{source_name}%"),
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    # 计算总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()

    # 应用排序
    if sort_by:
        if sort_by == "id":
            order_column = AudioSegment.id
        elif sort_by == "created_at":
            order_column = AudioSegment.created_at
        elif sort_by == "duration":
            order_column = AudioSegment.duration
        else:
            order_column = AudioSegment.created_at  # 默认

        if sort_order == "asc":
            stmt = stmt.order_by(order_column.asc())
        else:
            stmt = stmt.order_by(order_column.desc())
    else:
        # 默认按创建时间降序
        stmt = stmt.order_by(AudioSegment.created_at.desc())

    # 应用分页
    offset = (page - 1) * limit
    stmt = stmt.limit(limit).offset(offset)

    # 执行查询
    result = await db.execute(stmt)
    segments = result.scalars().all()

    # 转换为响应格式
    data = []
    for segment in segments:
        # 创建segment.__dict__副本并移除oss_url键
        segment_dict = segment.__dict__.copy()
        segment_dict.pop('oss_url', None)

        # 获取source_title
        source_title = segment.source.title if segment.source else None

        # 修复音频URL
        audio_url = _fix_audio_url_for_dev(segment.oss_url)

        response = AudioSegmentResponse(
            **segment_dict,
            source_title=source_title,
            oss_url=audio_url,
            is_favorite=False,  # 管理界面不需要收藏状态
        )
        data.append(response)

    # 返回分页结果
    return {
        "data": data,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if limit > 0 else 0,
    }


async def _process_audio_source_background(source_id: str, user_id: str):
    """
    后台处理音频源（模拟实现）

    在实际实现中，这里应该：
    1. 使用Celery任务队列
    2. 从OSS下载音频文件
    3. 调用音频处理服务进行分割和ASR识别
    4. 更新数据库状态
    """
    try:
        logger.info(f"开始后台处理音频源: {source_id}")

        # 模拟处理延迟
        await asyncio.sleep(5)

        logger.info(f"音频源后台处理完成: {source_id}")

    except Exception as e:
        logger.error(f"音频源后台处理失败: {source_id}, 错误: {str(e)}")


async def get_audio_stats(db: AsyncSession) -> dict:
    """
    获取音频统计数据
    
    返回:
        total: 音频片段总数
        approved: 已审核通过数量
        pending: 待审核数量
        rejected: 已拒绝数量
        users: 注册用户总数
        sources: 音频源总数
    """
    from sqlalchemy import select, func
    from shared.models.user import User
    
    # 统计音频片段总数
    total_result = await db.execute(select(func.count(AudioSegment.id)))
    total = total_result.scalar() or 0
    
    # 统计已审核通过数量
    approved_result = await db.execute(
        select(func.count(AudioSegment.id)).where(AudioSegment.review_status == "approved")
    )
    approved = approved_result.scalar() or 0
    
    # 统计待审核数量
    pending_result = await db.execute(
        select(func.count(AudioSegment.id)).where(AudioSegment.review_status == "pending")
    )
    pending = pending_result.scalar() or 0
    
    # 统计已拒绝数量
    rejected_result = await db.execute(
        select(func.count(AudioSegment.id)).where(AudioSegment.review_status == "rejected")
    )
    rejected = rejected_result.scalar() or 0
    
    # 统计用户总数
    users_result = await db.execute(select(func.count(User.id)))
    users = users_result.scalar() or 0
    
    # 统计音频源总数
    sources_result = await db.execute(select(func.count(AudioSource.id)))
    sources = sources_result.scalar() or 0
    
    return {
        "total": total,
        "approved": approved,
        "pending": pending,
        "rejected": rejected,
        "users": users,
        "sources": sources,
    }