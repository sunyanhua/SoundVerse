"""
日志配置
"""
import logging
import logging.handlers
import sys
from pathlib import Path

from config import settings


def setup_logging() -> None:
    """
    设置日志配置
    """
    # 创建日志目录
    log_file = Path(settings.LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 配置日志格式
    formatter = logging.Formatter(settings.LOG_FORMAT)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(settings.LOG_LEVEL)

    # 文件处理器
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(settings.LOG_LEVEL)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # 设置第三方库的日志级别
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    # 添加自定义过滤器（可选）
    class ContextFilter(logging.Filter):
        def filter(self, record):
            # 可以在这里添加额外的上下文信息
            return True

    root_logger.addFilter(ContextFilter())


def get_logger(name: str) -> logging.Logger:
    """
    获取命名日志记录器
    """
    return logging.getLogger(name)


# 预定义的日志记录器
logger = get_logger(__name__)


class RequestIdFilter(logging.Filter):
    """
    请求ID过滤器
    """
    def __init__(self, request_id: str = ""):
        super().__init__()
        self.request_id = request_id

    def filter(self, record):
        record.request_id = self.request_id
        return True


def setup_request_logging(request_id: str) -> None:
    """
    设置请求日志
    """
    logger = logging.getLogger()
    for handler in logger.handlers:
        handler.addFilter(RequestIdFilter(request_id))