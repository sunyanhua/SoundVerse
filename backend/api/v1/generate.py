"""
音频生成相关API
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_db
from shared.models.user import User
from shared.schemas.chat import (
    GenerateAudioRequest,
    GenerateAudioResponse,
    GeneratedAudioResponse,
    AudioTemplate,
    TemplateCategory,
    ShareAudioRequest,
    ShareAudioResponse,
)
from services.audio_generation_service import (
    generate_audio_from_template,
    get_audio_templates,
    get_template_categories,
    get_user_generated_audios,
    share_generated_audio,
    delete_generated_audio,
)
from .auth import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/templates", response_model=List[AudioTemplate])
async def list_audio_templates(
    category_id: str = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[AudioTemplate]:
    """
    获取音频模板列表
    """
    try:
        templates = await get_audio_templates(db, category_id)
        return templates
    except Exception as e:
        logger.error(f"获取音频模板失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取音频模板失败",
        )


@router.get("/categories", response_model=List[TemplateCategory])
async def list_template_categories(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[TemplateCategory]:
    """
    获取模板分类列表
    """
    try:
        categories = await get_template_categories(db)
        return categories
    except Exception as e:
        logger.error(f"获取模板分类失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取模板分类失败",
        )


@router.post("/audio", response_model=GenerateAudioResponse)
async def generate_audio(
    request: GenerateAudioRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GenerateAudioResponse:
    """
    生成音频
    """
    # 检查用户生成配额
    if current_user.daily_generate_count >= 10:  # 每日限制10次
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日音频生成次数已用完，请明天再试",
        )

    try:
        # 生成音频
        result = await generate_audio_from_template(
            db=db,
            user=current_user,
            template_id=request.template_id,
            variables=request.variables,
            voice_type=request.voice_type,
            background_music=request.background_music,
        )

        # 更新用户生成计数
        current_user.increment_generate_count()
        await db.commit()

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"生成音频失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成音频失败",
        )


@router.get("/my-audios", response_model=List[GeneratedAudioResponse])
async def get_my_generated_audios(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[GeneratedAudioResponse]:
    """
    获取用户生成的音频列表
    """
    try:
        audios = await get_user_generated_audios(db, current_user.id, limit, offset)
        return audios
    except Exception as e:
        logger.error(f"获取用户音频列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户音频列表失败",
        )


@router.get("/audio/{audio_id}", response_model=GeneratedAudioResponse)
async def get_generated_audio_detail(
    audio_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> GeneratedAudioResponse:
    """
    获取生成的音频详情
    """
    try:
        # 这里需要实现获取音频详情的逻辑
        # 暂时返回模拟数据
        return GeneratedAudioResponse(
            id=audio_id,
            user_id=current_user.id,
            template_id="birthday_template",
            title="生日祝福音频",
            text_content="祝你生日快乐！",
            voice_type="default",
            duration=15.5,
            file_size=102400,
            format="mp3",
            oss_key="audio/generated/test.mp3",
            oss_url="https://oss.example.com/audio/generated/test.mp3",
            share_code="ABCD1234",
            play_count=5,
            share_count=2,
            download_count=1,
            review_status="approved",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            share_url="https://soundverse.example.com/share/ABCD1234",
        )
    except Exception as e:
        logger.error(f"获取音频详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取音频详情失败",
        )


@router.post("/audio/{audio_id}/share", response_model=ShareAudioResponse)
async def share_audio(
    audio_id: str,
    request: ShareAudioRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ShareAudioResponse:
    """
    分享生成的音频
    """
    try:
        result = await share_generated_audio(
            db=db,
            audio_id=audio_id,
            user_id=current_user.id,
            share_to=request.share_to,
            message=request.message,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"分享音频失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="分享音频失败",
        )


@router.delete("/audio/{audio_id}")
async def delete_generated_audio(
    audio_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    删除生成的音频
    """
    try:
        success = await delete_generated_audio(db, audio_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限删除此音频",
            )
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除音频失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除音频失败",
        )


@router.post("/audio/{audio_id}/play")
async def record_audio_play(
    audio_id: str,
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


@router.post("/audio/{audio_id}/download")
async def record_audio_download(
    audio_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    记录音频下载（用于统计）
    """
    try:
        # 这里应该实现下载记录逻辑
        return {"message": "下载记录成功"}
    except Exception as e:
        logger.error(f"记录下载失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="记录下载失败",
        )


@router.get("/preview/{template_id}")
async def preview_audio_template(
    template_id: str,
    variables: str = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    预览音频模板（返回示例文本）
    """
    try:
        # 这里应该实现模板预览逻辑
        # 暂时返回模拟数据
        preview_text = ""

        if template_id == "birthday_template":
            preview_text = "亲爱的{name}，祝你生日快乐！愿你的每一天都充满阳光和欢笑。"
        elif template_id == "love_template":
            preview_text = "亲爱的{name}，我想对你说：{message}"
        elif template_id == "apology_template":
            preview_text = "对不起{name}，我为{reason}感到抱歉。希望你能原谅我。"

        # 处理变量
        if variables:
            # 这里应该解析variables并替换
            pass

        return {
            "template_id": template_id,
            "preview_text": preview_text,
            "estimated_duration": 10.5,
        }
    except Exception as e:
        logger.error(f"预览模板失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="预览模板失败",
        )