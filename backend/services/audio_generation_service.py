"""
音频生成服务
"""
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.chat import GeneratedAudio
from shared.models.user import User
from shared.schemas.chat import (
    AudioTemplate,
    TemplateCategory,
    GenerateAudioResponse,
    GeneratedAudioResponse,
    ShareAudioResponse,
)
from config import settings

logger = logging.getLogger(__name__)


# 音频模板数据（在实际应用中应该存储在数据库中）
AUDIO_TEMPLATES = {
    "birthday_template": AudioTemplate(
        id="birthday_template",
        name="生日祝福",
        description="生成个性化的生日祝福音频",
        category="祝福",
        example_text="亲爱的{name}，祝你生日快乐！愿你的每一天都充满阳光和欢笑。",
        variable_fields=[
            {"name": "name", "label": "收件人姓名", "required": True},
            {"name": "relationship", "label": "关系", "required": False},
        ],
        background_music_options=["happy_birthday", "celebratory", "gentle"],
        voice_options=["friendly_female", "warm_male", "cheerful_child"],
        estimated_duration=15.0,
    ),
    "love_template": AudioTemplate(
        id="love_template",
        name="深情表白",
        description="生成浪漫的表白音频",
        category="表白",
        example_text="亲爱的{name}，我想对你说：{message}",
        variable_fields=[
            {"name": "name", "label": "对方姓名", "required": True},
            {"name": "message", "label": "表白内容", "required": True},
            {"name": "your_name", "label": "你的姓名", "required": False},
        ],
        background_music_options=["romantic", "soft_piano", "love_song"],
        voice_options=["romantic_female", "deep_male", "gentle_unisex"],
        estimated_duration=20.0,
    ),
    "apology_template": AudioTemplate(
        id="apology_template",
        name="真诚道歉",
        description="生成真诚的道歉音频",
        category="道歉",
        example_text="对不起{name}，我为{reason}感到抱歉。希望你能原谅我。",
        variable_fields=[
            {"name": "name", "label": "对方姓名", "required": True},
            {"name": "reason", "label": "道歉原因", "required": True},
            {"name": "promise", "label": "承诺改进", "required": False},
        ],
        background_music_options=["sincere", "calm", "reflective"],
        voice_options=["sincere_female", "earnest_male", "soft_unisex"],
        estimated_duration=18.0,
    ),
    "prank_template": AudioTemplate(
        id="prank_template",
        name="趣味整蛊",
        description="生成有趣的整蛊音频",
        category="整蛊",
        example_text="哈哈哈，你被整蛊了！{target_name}，{prank_content}",
        variable_fields=[
            {"name": "target_name", "label": "整蛊对象", "required": True},
            {"name": "prank_content", "label": "整蛊内容", "required": True},
        ],
        background_music_options=["funny", "surprise", "playful"],
        voice_options=["funny_male", "playful_female", "cartoon_voice"],
        estimated_duration=12.0,
    ),
}

TEMPLATE_CATEGORIES = [
    TemplateCategory(
        id="blessing",
        name="祝福",
        description="生日、节日、庆典等祝福音频",
        icon="🎂",
        templates=[AUDIO_TEMPLATES["birthday_template"]],
    ),
    TemplateCategory(
        id="love",
        name="表白",
        description="表白、情话、浪漫告白音频",
        icon="❤️",
        templates=[AUDIO_TEMPLATES["love_template"]],
    ),
    TemplateCategory(
        id="apology",
        name="道歉",
        description="道歉、认错、和解音频",
        icon="🙏",
        templates=[AUDIO_TEMPLATES["apology_template"]],
    ),
    TemplateCategory(
        id="prank",
        name="整蛊",
        description="整蛊、玩笑、趣味音频",
        icon="😜",
        templates=[AUDIO_TEMPLATES["prank_template"]],
    ),
]


async def get_audio_templates(
    db: AsyncSession,
    category_id: Optional[str] = None,
) -> List[AudioTemplate]:
    """
    获取音频模板列表
    """
    if category_id:
        # 按分类过滤
        category = next((c for c in TEMPLATE_CATEGORIES if c.id == category_id), None)
        if category:
            return category.templates
        else:
            return []
    else:
        # 返回所有模板
        return list(AUDIO_TEMPLATES.values())


async def get_template_categories(db: AsyncSession) -> List[TemplateCategory]:
    """
    获取模板分类列表
    """
    return TEMPLATE_CATEGORIES


async def generate_audio_from_template(
    db: AsyncSession,
    user: User,
    template_id: str,
    variables: Dict[str, str],
    voice_type: Optional[str] = None,
    background_music: Optional[str] = None,
) -> GenerateAudioResponse:
    """
    根据模板生成音频
    """
    # 获取模板
    template = AUDIO_TEMPLATES.get(template_id)
    if not template:
        raise ValueError(f"模板不存在: {template_id}")

    # 验证必填变量
    for field in template.variable_fields:
        if field["required"] and field["name"] not in variables:
            raise ValueError(f"缺少必填字段: {field['label']}")

    # 生成文本内容
    text_content = template.example_text
    for key, value in variables.items():
        placeholder = "{" + key + "}"
        text_content = text_content.replace(placeholder, value)

    # 生成分享码
    share_code = generate_share_code()

    # 创建生成的音频记录
    generated_audio = GeneratedAudio(
        user_id=user.id,
        template_id=template_id,
        title=f"{template.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        text_content=text_content,
        voice_type=voice_type or template.voice_options[0],
        background_music=background_music,
        duration=template.estimated_duration,
        file_size=0,  # 实际应从生成的文件获取
        oss_key=f"audio/generated/{user.id}/{share_code}.mp3",
        oss_url=f"{settings.OSS_PUBLIC_DOMAIN}/audio/generated/{user.id}/{share_code}.mp3" if hasattr(settings, 'OSS_PUBLIC_DOMAIN') and settings.OSS_PUBLIC_DOMAIN else f"https://{settings.OSS_BUCKET}.{settings.OSS_ENDPOINT}/audio/generated/{user.id}/{share_code}.mp3",
        share_code=share_code,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(generated_audio)
    await db.commit()
    await db.refresh(generated_audio)

    # 在实际实现中，这里应该：
    # 1. 调用阿里云TTS API合成语音
    # 2. 混合背景音乐
    # 3. 上传到OSS
    # 4. 更新音频记录的文件信息

    logger.info(f"用户 {user.id} 生成音频: {generated_audio.id}")

    return GenerateAudioResponse(
        audio=GeneratedAudioResponse(
            **generated_audio.__dict__,
            share_url=generated_audio.share_url,
        ),
        estimated_wait_time=5.0,  # 模拟等待时间
    )


async def get_user_generated_audios(
    db: AsyncSession,
    user_id: str,
    limit: int,
    offset: int,
) -> List[GeneratedAudioResponse]:
    """
    获取用户生成的音频列表
    """
    stmt = select(GeneratedAudio).where(
        GeneratedAudio.user_id == user_id,
    ).order_by(
        desc(GeneratedAudio.created_at),
    ).limit(limit).offset(offset)

    result = await db.execute(stmt)
    audios = result.scalars().all()

    responses = []
    for audio in audios:
        responses.append(GeneratedAudioResponse(
            **audio.__dict__,
            share_url=audio.share_url,
        ))

    return responses


async def share_generated_audio(
    db: AsyncSession,
    audio_id: str,
    user_id: str,
    share_to: Optional[str],
    message: Optional[str],
) -> ShareAudioResponse:
    """
    分享生成的音频
    """
    # 查找音频
    stmt = select(GeneratedAudio).where(
        GeneratedAudio.id == audio_id,
        GeneratedAudio.user_id == user_id,
    )
    result = await db.execute(stmt)
    audio = result.scalar_one_or_none()

    if not audio:
        raise ValueError("音频不存在")

    # 更新分享计数
    audio.increment_share_count()
    await db.commit()

    # 生成分享响应
    response = ShareAudioResponse(
        share_url=audio.share_url,
        qr_code_url=f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={audio.share_url}",
        short_url=audio.share_url,  # 实际应该生成短链接
    )

    logger.info(f"用户 {user_id} 分享音频: {audio_id}")

    return response


async def delete_generated_audio(
    db: AsyncSession,
    audio_id: str,
    user_id: str,
) -> bool:
    """
    删除生成的音频
    """
    stmt = select(GeneratedAudio).where(
        GeneratedAudio.id == audio_id,
        GeneratedAudio.user_id == user_id,
    )
    result = await db.execute(stmt)
    audio = result.scalar_one_or_none()

    if not audio:
        return False

    # 在实际实现中，这里应该：
    # 1. 删除OSS上的文件
    # 2. 删除数据库记录

    # 这里只标记为删除（软删除）
    audio.review_status = "deleted"
    await db.commit()

    return True


def generate_share_code() -> str:
    """
    生成分享码
    """
    # 生成8位随机码（字母和数字）
    import random
    import string

    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=8))


async def get_generated_audio_by_share_code(
    db: AsyncSession,
    share_code: str,
) -> Optional[GeneratedAudioResponse]:
    """
    通过分享码获取生成的音频
    """
    stmt = select(GeneratedAudio).where(
        GeneratedAudio.share_code == share_code,
        GeneratedAudio.review_status == "approved",
    )
    result = await db.execute(stmt)
    audio = result.scalar_one_or_none()

    if not audio:
        return None

    return GeneratedAudioResponse(
        **audio.__dict__,
        share_url=audio.share_url,
    )