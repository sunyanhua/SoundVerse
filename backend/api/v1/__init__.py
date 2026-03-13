"""
API v1 路由
"""
from fastapi import APIRouter

from . import auth, audio, chat, generate

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(audio.router, prefix="/audio", tags=["音频"])
api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
api_router.include_router(generate.router, prefix="/generate", tags=["生成"])