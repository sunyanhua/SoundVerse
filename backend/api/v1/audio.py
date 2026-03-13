"""
音频相关API
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_db
from shared.models.user import User
from shared.schemas.audio import (
    AudioUploadRequest,
    AudioUploadResponse,
    AudioProcessingStatus,
    AudioSearchRequest,
    AudioSearchResponse,
    AudioSegmentResponse,
    FavoriteSegmentCreate,
    FavoriteSegmentResponse,
)
from services.audio_service import (
    upload_audio,
    get_audio_processing_status,
    search_audio_segments,
    get_audio_segment,
    favorite_audio_segment,
    get_user_favorites,
    delete_audio_source,
)
from .auth import get_current_active_user
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload", response_model=AudioUploadResponse)
async def upload_audio_file(
    request: AudioUploadRequest,
    audio_file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AudioUploadResponse:
    """
    上传音频文件
    """
    # 检查文件大小
    if audio_file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB)",
        )

    # 检查文件类型
    file_extension = audio_file.filename.split('.')[-1].lower() if '.' in audio_file.filename else ''
    if file_extension not in settings.ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型，支持的类型: {', '.join(settings.ALLOWED_AUDIO_TYPES)}",
        )

    try:
        response = await upload_audio(
            db=db,
            user=current_user,
            audio_file=audio_file,
            request=request,
        )
        return response
    except Exception as e:
        logger.error(f"上传音频失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="上传音频失败",
        )


@router.get("/processing/{processing_id}", response_model=AudioProcessingStatus)
async def get_processing_status(
    processing_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AudioProcessingStatus:
    """
    获取音频处理状态
    """
    try:
        status_info = await get_audio_processing_status(db, processing_id, current_user.id)
        return status_info
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"获取处理状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取处理状态失败",
        )


@router.post("/search", response_model=AudioSearchResponse)
async def search_audio(
    request: AudioSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AudioSearchResponse:
    """
    搜索音频片段
    """
    try:
        # 检查用户配额
        # 这里可以添加配额检查逻辑

        result = await search_audio_segments(db, request, current_user.id)
        return result
    except Exception as e:
        logger.error(f"搜索音频失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜索音频失败",
        )


@router.get("/segment/{segment_id}", response_model=AudioSegmentResponse)
async def get_segment_detail(
    segment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AudioSegmentResponse:
    """
    获取音频片段详情
    """
    try:
        segment = await get_audio_segment(db, segment_id, current_user.id)
        return segment
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"获取音频片段失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取音频片段失败",
        )


@router.post("/favorite", response_model=FavoriteSegmentResponse)
async def add_to_favorites(
    request: FavoriteSegmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> FavoriteSegmentResponse:
    """
    收藏音频片段
    """
    try:
        favorite = await favorite_audio_segment(db, current_user.id, request.segment_id)
        return favorite
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"收藏音频失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="收藏音频失败",
        )


@router.get("/favorites", response_model=List[FavoriteSegmentResponse])
async def get_favorites(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[FavoriteSegmentResponse]:
    """
    获取用户收藏的音频片段
    """
    try:
        favorites = await get_user_favorites(db, current_user.id, limit, offset)
        return favorites
    except Exception as e:
        logger.error(f"获取收藏列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取收藏列表失败",
        )


@router.delete("/favorite/{segment_id}")
async def remove_from_favorites(
    segment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    取消收藏音频片段
    """
    try:
        # 这里需要实现取消收藏的逻辑
        # 暂时返回成功
        return {"message": "取消收藏成功"}
    except Exception as e:
        logger.error(f"取消收藏失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="取消收藏失败",
        )


@router.delete("/source/{source_id}")
async def delete_source(
    source_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    删除音频源（仅限管理员或上传者）
    """
    try:
        success = await delete_audio_source(db, source_id, current_user)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限删除此音频源",
            )
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除音频源失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除音频源失败",
        )


@router.get("/recommended", response_model=List[AudioSegmentResponse])
async def get_recommended_audios(
    limit: int = 10,
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[AudioSegmentResponse]:
    """
    获取推荐音频片段
    """
    try:
        # 这里应该实现推荐算法
        # 暂时返回空列表
        return []
    except Exception as e:
        logger.error(f"获取推荐音频失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取推荐音频失败",
        )


@router.post("/play/{segment_id}")
async def record_play(
    segment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    记录音频播放（用于统计）
    """
    try:
        # 这里应该实现播放记录逻辑
        return {"message": "播放记录成功"}
    except Exception as e:
        logger.error(f"记录播放失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="记录播放失败",
        )