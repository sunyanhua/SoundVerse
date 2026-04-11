"""
聊天相关API
"""
import logging
import random
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import tempfile
import os

from shared.database.session import get_db
from shared.models.user import User
from shared.models.chat import PresetPrompt, ChatMessage
from shared.schemas.chat import (
    ChatMessageCreate,
    ChatResponse,
    ChatSessionResponse,
    ChatHistoryRequest,
    ChatHistoryResponse,
    ChatMessageUpdate,
    PresetPromptCreate,
    PresetPromptResponse,
    LikeRequest,
)
from services.chat_service import (
    process_chat_message,
    get_chat_sessions,
    get_chat_history,
    update_message_feedback,
    create_chat_session,
    delete_chat_session,
    generate_chat_suggestions,
)
from ai_models.asr_service import recognize_audio_file
from .auth import get_current_active_user
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# 可选的认证方案（auto_error=False，允许token为空）
optional_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


# 模拟用户依赖，支持demo模式和jwt模式
async def get_current_user_or_mock(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(optional_oauth2_scheme),
) -> User:
    """
    获取当前用户，根据AUTH_MODE配置决定认证策略：
    - demo模式：直接返回模拟用户
    - jwt模式：尝试JWT认证，失败则返回模拟用户
    """
    # 固定模拟用户ID
    MOCK_USER_ID = "demo-user-001"

    # 根据认证模式处理
    if settings.AUTH_MODE == "demo":
        logger.info(f"demo模式：使用模拟用户 (ID: {MOCK_USER_ID})")
        try:
            # 尝试从数据库获取模拟用户
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.id == MOCK_USER_ID))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                return existing_user

            # 创建模拟用户
            mock_user = User(
                id=MOCK_USER_ID,
                wechat_openid=f"mock-wechat-{MOCK_USER_ID}",
                nickname="模拟用户",
                avatar_url="https://example.com/avatar.jpg",
                is_active=True,
                is_premium=False,
                is_admin=False,
                daily_chat_count=0,
                daily_generate_count=0,
                total_chat_count=0,
                total_generate_count=0,
                preferred_voice="default",
                preferred_language="zh-CN",
                notification_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(mock_user)
            await db.commit()
            await db.refresh(mock_user)
            return mock_user
        except Exception as e:
            logger.error(f"数据库操作失败，使用纯模拟用户: {e}")
            # 返回一个不依赖于数据库的模拟用户
            return User(
                id=MOCK_USER_ID,
                wechat_openid=f"mock-wechat-{MOCK_USER_ID}",
                nickname="模拟用户",
                avatar_url="https://example.com/avatar.jpg",
                is_active=True,
                is_premium=False,
                is_admin=False,
                daily_chat_count=0,
                daily_generate_count=0,
                total_chat_count=0,
                total_generate_count=0,
                preferred_voice="default",
                preferred_language="zh-CN",
                notification_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

    # jwt模式：尝试认证，如果失败则使用模拟用户
    else:  # settings.AUTH_MODE == "jwt"
        if token:
            # 有token，尝试认证
            try:
                from services.user_service import get_current_user
                user = await get_current_user(db, token)
                if user:
                    return user
                else:
                    logger.warning("jwt模式：token无效，使用模拟用户")
            except Exception as e:
                logger.error(f"jwt模式：认证过程中出错，使用模拟用户: {e}")
        else:
            logger.warning("jwt模式：未提供token，使用模拟用户")

        # 使用模拟用户（与demo模式相同的逻辑）
        try:
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.id == MOCK_USER_ID))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                return existing_user

            # 创建模拟用户
            mock_user = User(
                id=MOCK_USER_ID,
                wechat_openid=f"mock-wechat-{MOCK_USER_ID}",
                nickname="模拟用户",
                avatar_url="https://example.com/avatar.jpg",
                is_active=True,
                is_premium=False,
                is_admin=False,
                daily_chat_count=0,
                daily_generate_count=0,
                total_chat_count=0,
                total_generate_count=0,
                preferred_voice="default",
                preferred_language="zh-CN",
                notification_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(mock_user)
            await db.commit()
            await db.refresh(mock_user)
            return mock_user
        except Exception as e:
            logger.error(f"jwt模式：数据库操作失败，使用纯模拟用户: {e}")
            return User(
                id=MOCK_USER_ID,
                wechat_openid=f"mock-wechat-{MOCK_USER_ID}",
                nickname="模拟用户",
                avatar_url="https://example.com/avatar.jpg",
                is_active=True,
                is_premium=False,
                is_admin=False,
                daily_chat_count=0,
                daily_generate_count=0,
                total_chat_count=0,
                total_generate_count=0,
                preferred_voice="default",
                preferred_language="zh-CN",
                notification_enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )


@router.post("/message", response_model=ChatResponse)
async def send_chat_message(
    request: ChatMessageCreate,
    current_user: User = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    发送聊天消息
    """
    # 检查用户聊天配额（开发环境下跳过）
    if settings.ENVIRONMENT != "development" and current_user.daily_chat_count >= 50:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="今日聊天次数已用完，请明天再试",
        )

    try:
        # 处理聊天消息
        response = await process_chat_message(
            db=db,
            user=current_user,
            message=request.content,
            session_id=request.session_id,
        )

        # 更新用户聊天计数
        current_user.increment_chat_count()
        await db.commit()

        return response
    except Exception as e:
        logger.error(f"处理聊天消息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理聊天消息失败",
        )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[ChatSessionResponse]:
    """
    获取用户的聊天会话列表
    """
    try:
        sessions = await get_chat_sessions(db, current_user.id, limit, offset)
        return sessions
    except Exception as e:
        logger.error(f"获取聊天会话列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取聊天会话列表失败",
        )


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_new_session(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """
    创建新的聊天会话
    """
    try:
        session = await create_chat_session(db, current_user.id)
        return session
    except Exception as e:
        logger.error(f"创建聊天会话失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建聊天会话失败",
        )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session_detail(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSessionResponse:
    """
    获取聊天会话详情
    """
    try:
        # 这里需要实现获取会话详情的逻辑
        # 暂时返回简单响应
        return ChatSessionResponse(
            id=session_id,
            user_id=current_user.id,
            title="聊天会话",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
    except Exception as e:
        logger.error(f"获取聊天会话详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取聊天会话详情失败",
        )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    删除聊天会话
    """
    try:
        success = await delete_chat_session(db, session_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="没有权限删除此会话",
            )
        return {"message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除聊天会话失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除聊天会话失败",
        )


@router.post("/history", response_model=ChatHistoryResponse)
async def get_chat_history_endpoint(
    request: ChatHistoryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """
    获取聊天历史
    """
    try:
        history = await get_chat_history(
            db=db,
            user_id=current_user.id,
            session_id=request.session_id,
            limit=request.limit,
            offset=request.offset,
        )
        return history
    except Exception as e:
        logger.error(f"获取聊天历史失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取聊天历史失败",
        )


@router.put("/messages/{message_id}")
async def update_message(
    message_id: str,
    request: ChatMessageUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    更新消息（如反馈）
    """
    try:
        success = await update_message_feedback(
            db=db,
            message_id=message_id,
            user_id=current_user.id,
            feedback=request.user_feedback,
            feedback_reason=request.feedback_reason,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="消息不存在或没有权限",
            )

        return {"message": "更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新消息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新消息失败",
        )


@router.get("/suggestions")
async def get_chat_suggestions(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    获取聊天建议（话题、问题等）
    """
    try:
        # 生成基于用户聊天历史的建议
        suggestions = await generate_chat_suggestions(db, current_user.id)
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"获取聊天建议失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取聊天建议失败",
        )


@router.get("/context/{session_id}")
async def get_chat_context(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    获取聊天上下文（用于继续对话）
    """
    try:
        # 这里应该实现上下文提取逻辑
        # 暂时返回空上下文
        return {
            "session_id": session_id,
            "context_summary": "",
            "recent_messages": [],
        }
    except Exception as e:
        logger.error(f"获取聊天上下文失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取聊天上下文失败",
        )


@router.post("/test/audio-match")
async def test_audio_match(
    text: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    测试音频匹配（开发用）
    """
    try:
        # 这里应该实现音频匹配测试逻辑
        # 暂时返回模拟结果
        return {
            "query": text,
            "matched_audio": {
                "id": "test-segment-1",
                "title": "测试音频片段",
                "transcription": "这是一个测试音频片段",
                "similarity_score": 0.85,
                "audio_url": "https://example.com/test-audio.mp3",
            },
            "processing_time_ms": 150.5,
        }
    except Exception as e:
        logger.error(f"测试音频匹配失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="测试音频匹配失败",
        )


@router.post("/voice")
async def process_voice_message(
    audio: UploadFile = File(...),
    session_id: str = Form(None),
    format: str = Form("mp3"),
    sample_rate: int = Form(16000),
    current_user: User = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    处理语音消息：接收音频文件，进行ASR识别，然后处理为聊天消息
    """
    try:
        # 检查文件大小（限制为5MB）
        audio.file.seek(0, 2)  # 移动到文件末尾
        file_size = audio.file.tell()
        audio.file.seek(0)  # 重置文件指针
        max_size = 5 * 1024 * 1024  # 5MB
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"音频文件大小超过限制（{max_size / 1024 / 1024}MB）",
            )

        # 创建临时文件保存音频
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{format}") as tmp_file:
            # 读取音频文件内容
            content = await audio.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            # 调用ASR服务识别音频
            text = await recognize_audio_file(
                tmp_file_path,
                language="zh-CN",
                sample_rate=sample_rate,
                format=format,
            )

            if not text:
                return {
                    "success": False,
                    "message": "语音识别失败，未识别到有效语音",
                }

            # 使用识别出的文本调用现有的聊天消息处理逻辑
            response = await process_chat_message(
                db=db,
                user=current_user,
                message=text,
                session_id=session_id,
            )

            # 更新用户聊天计数
            current_user.increment_chat_count()
            await db.commit()

            return {
                "success": True,
                "text": text,
                "chat_response": response.dict() if hasattr(response, 'dict') else response,
            }

        finally:
            # 删除临时文件
            try:
                os.unlink(tmp_file_path)
            except Exception as e:
                logger.warning(f"删除临时文件失败: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理语音消息失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理语音消息失败",
        )


@router.post("/preset-prompts", response_model=PresetPromptResponse)
async def create_preset_prompt(
    request: PresetPromptCreate,
    current_user: User = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
) -> PresetPromptResponse:
    """
    创建预置提示词（点赞保存）
    """
    try:
        from sqlalchemy import select

        # 检查原始消息是否存在（如果提供了original_message_id）
        original_message = None
        if request.original_message_id:
            result = await db.execute(
                select(ChatMessage).where(ChatMessage.id == request.original_message_id)
            )
            original_message = result.scalar_one_or_none()
            if not original_message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="原始消息不存在",
                )

        # 创建预置提示词
        preset_prompt = PresetPrompt(
            user_id=current_user.id,
            original_message_id=request.original_message_id,
            query_text=request.query_text,
            category=request.category,
            emotion=request.emotion,
            tags=request.tags or [],
            use_count=0,
            like_count=1,
            review_status="pending",
        )

        db.add(preset_prompt)
        await db.commit()
        await db.refresh(preset_prompt)

        # 转换为响应模型
        return PresetPromptResponse(
            id=preset_prompt.id,
            user_id=preset_prompt.user_id,
            original_message_id=preset_prompt.original_message_id,
            query_text=preset_prompt.query_text,
            category=preset_prompt.category,
            emotion=preset_prompt.emotion,
            tags=preset_prompt.tags,
            use_count=preset_prompt.use_count,
            like_count=preset_prompt.like_count,
            review_status=preset_prompt.review_status,
            created_at=preset_prompt.created_at,
            updated_at=preset_prompt.updated_at,
            user_nickname=current_user.nickname,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建预置提示词失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建预置提示词失败",
        )


@router.get("/preset-prompts/random", response_model=List[PresetPromptResponse])
async def get_random_preset_prompts(
    count: int = 3,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
) -> List[PresetPromptResponse]:
    """
    获取随机预置提示词
    返回当前用户自己的提示词（无论审核状态）+ 其他用户已审核通过的提示词
    """
    try:
        from sqlalchemy import select
        from sqlalchemy.sql import or_, and_

        # 构建查询：当前用户的所有提示词 + 其他用户已审核通过的提示词
        # 过滤掉 query_text 为空的记录（schema要求至少1个字符）
        query = select(PresetPrompt).where(
            and_(
                PresetPrompt.query_text.isnot(None),
                PresetPrompt.query_text != "",
                or_(
                    PresetPrompt.user_id == current_user.id,  # 当前用户的所有提示词
                    PresetPrompt.review_status == "approved"   # 其他用户已审核通过的
                )
            )
        )

        if category:
            query = query.where(PresetPrompt.category == category)

        # 获取所有匹配的记录，然后在Python中随机选择
        # 避免不同数据库random()函数的差异问题
        result = await db.execute(query)
        all_prompts = list(result.scalars().all())

        # Python中随机打乱并取前count个
        random.shuffle(all_prompts)
        preset_prompts = all_prompts[:count]

        # 转换为响应模型列表
        responses = []
        for prompt in preset_prompts:
            # 获取用户昵称
            from shared.models.user import User
            user_result = await db.execute(
                select(User).where(User.id == prompt.user_id)
            )
            user = user_result.scalar_one_or_none()

            responses.append(
                PresetPromptResponse(
                    id=prompt.id,
                    user_id=prompt.user_id,
                    original_message_id=prompt.original_message_id,
                    query_text=prompt.query_text,
                    category=prompt.category,
                    emotion=prompt.emotion,
                    tags=prompt.tags,
                    use_count=prompt.use_count,
                    like_count=prompt.like_count,
                    review_status=prompt.review_status,
                    created_at=prompt.created_at,
                    updated_at=prompt.updated_at,
                    user_nickname=user.nickname if user else None,
                )
            )

        return responses

    except Exception as e:
        logger.error(f"获取随机预置提示词失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取随机预置提示词失败",
        )


@router.put("/messages/{message_id}/like")
async def like_message(
    message_id: str,
    request: LikeRequest,
    current_user: User = Depends(get_current_user_or_mock),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    点赞消息并可选保存为预设提示词
    如果点赞的是助手回复，会保存对应的用户提问词
    """
    try:
        from sqlalchemy import select, desc

        # 查找消息
        result = await db.execute(
            select(ChatMessage).where(ChatMessage.id == message_id)
        )
        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="消息不存在",
            )

        # 更新消息的点赞状态
        if request.like:
            message.set_feedback("like", "用户点赞")
        else:
            message.set_feedback(None, None)  # 取消点赞

        # 如果用户选择保存为预设提示词
        if request.like and request.save_as_preset:
            # 确定要保存的查询文本
            query_text_to_save = None
            original_message_id_to_save = None

            if message.role == "assistant":
                # 如果点赞的是助手回复，查找同一会话中该消息之前的用户提问
                user_msg_result = await db.execute(
                    select(ChatMessage)
                    .where(
                        ChatMessage.session_id == message.session_id,
                        ChatMessage.role == "user",
                        ChatMessage.created_at < message.created_at,
                    )
                    .order_by(desc(ChatMessage.created_at))
                    .limit(1)
                )
                user_message = user_msg_result.scalar_one_or_none()

                if user_message:
                    query_text_to_save = user_message.content
                    original_message_id_to_save = user_message.id
                    logger.info(f"点赞助手回复，保存对应的用户提问: '{query_text_to_save[:50]}...'")
                else:
                    # 找不到对应的用户提问，使用助手回复前的内容（备选）
                    query_text_to_save = message.content
                    original_message_id_to_save = message_id
                    logger.warning(f"找不到助手回复对应的用户提问，使用助手内容作为备选")
            else:
                # 如果点赞的是用户消息，直接保存该消息内容
                query_text_to_save = message.content
                original_message_id_to_save = message_id

            # 检查是否已存在相同的预设提示词（基于用户提问内容）
            existing_result = await db.execute(
                select(PresetPrompt).where(
                    PresetPrompt.query_text == query_text_to_save,
                    PresetPrompt.user_id == current_user.id,
                )
            )
            existing_prompt = existing_result.scalar_one_or_none()

            if not existing_prompt:
                # 创建新的预设提示词
                preset_prompt = PresetPrompt(
                    user_id=current_user.id,
                    original_message_id=original_message_id_to_save,
                    query_text=query_text_to_save,
                    category=request.category,
                    emotion=None,  # 可以从消息中提取情感，这里暂时留空
                    tags=request.tags or [],
                    use_count=0,
                    like_count=1,
                    review_status="pending",
                )
                db.add(preset_prompt)
                logger.info(f"创建新的预设提示词: '{query_text_to_save[:50]}...'")
            else:
                # 更新现有预设提示词的分类和标签
                if request.category:
                    existing_prompt.category = request.category
                if request.tags:
                    existing_prompt.tags = request.tags
                existing_prompt.like_count += 1
                logger.info(f"更新现有预设提示词，点赞数增加到 {existing_prompt.like_count}")

        await db.commit()

        return {
            "message": "操作成功",
            "liked": request.like,
            "saved_as_preset": request.like and request.save_as_preset,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"点赞消息失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="点赞消息失败",
        )