"""
SoundVerse 后端服务主入口
"""
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from config import settings
from shared.database.session import get_db
from shared.utils.logging import setup_logging
from api.v1 import api_router

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    """
    # 启动时
    logger.info("Starting SoundVerse backend service...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # 初始化数据库连接等
    from shared.database.session import init_db
    await init_db()

    # 初始化 AI 服务
    from ai_models.nlp_service import init_nlp_service
    await init_nlp_service()

    from ai_models.asr_service import init_asr_service
    await init_asr_service()

    # 初始化向量索引
    from services.search_service import init_vector_index
    await init_vector_index()

    # 初始化LLM服务
    from ai_models.llm_service import init_llm_service
    await init_llm_service()

    yield

    # 关闭时
    logger.info("Shutting down SoundVerse backend service...")
    # 清理资源


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用
    """
    app = FastAPI(
        title="SoundVerse API",
        description="听听·原声态后端 API 服务",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # 添加中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

    # 添加全局异常处理
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.detail,
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "Internal server error",
                "data": None,
            },
        )

    # 添加健康检查端点
    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """健康检查端点"""
        return {
            "status": "healthy",
            "service": "soundverse-backend",
            "version": "1.0.0",
        }

    @app.get("/")
    async def root():
        """根端点"""
        return {
            "message": "Welcome to SoundVerse API",
            "docs": "/docs",
            "version": "1.0.0",
        }

    # 添加 Prometheus 指标端点
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    # 注册 API 路由
    app.include_router(api_router, prefix="/api/v1")

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning",
    )