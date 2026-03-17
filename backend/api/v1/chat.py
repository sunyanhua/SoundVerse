"""
聊天相关API
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
import tempfile
import os

from shared.database.session import get_db
from shared.models.user import User
from shared.schemas.chat import (
    ChatMessageCreate,
    ChatResponse,
    ChatSessionResponse,
    ChatHistoryRequest,
    ChatHistoryResponse,
    ChatMessageUpdate,
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


# 开发模式下的模拟用户依赖
async def get_current_user_or_mock(
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前用户，开发模式下返回模拟用户，生产模式下要求认证
    """
    # 开发模式下直接返回模拟用户
    if settings.DEBUG:
        logger.warning("开发模式：使用模拟用户")
        try:
            # 尝试从数据库获取一个用户，如果没有则创建
            from sqlalchemy import select
            result = await db.execute(select(User).limit(1))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                return existing_user

            # 创建测试用户
            from uuid import uuid4
            user_id = str(uuid4())
            test_user = User(
                id=user_id,
                wechat_openid=f"dev-wechat-{user_id}",
                nickname="测试用户",
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
            db.add(test_user)
            await db.commit()
            await db.refresh(test_user)
            return test_user
        except Exception as e:
            logger.error(f"数据库操作失败，使用纯模拟用户: {e}")
            # 返回一个不依赖于数据库的模拟用户
            from uuid import uuid4
            user_id = str(uuid4())
            return User(
                id=user_id,
                wechat_openid=f"dev-wechat-{user_id}",
                nickname="测试用户",
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

    # 生产模式要求认证
    try:
        return await get_current_active_user()
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录认证",
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