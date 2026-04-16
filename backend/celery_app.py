"""
Celery配置和任务定义
"""
import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from config import settings

# 设置默认的Django设置模块
os.environ.setdefault('FORKED_BY_MULTIPROCESSING', '1')

# 创建Celery应用
celery_app = Celery(
    'soundverse',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=['tasks'],
)

# 配置Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=5 * 60 * 60,  # 5小时硬限制（处理2小时长节目需要充足时间）
    task_soft_time_limit=4 * 60 * 60,  # 4小时软限制
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_reject_on_worker_lost=False,  # 禁用：Worker丢失时不重新投递任务，避免重复处理
    task_default_retry_delay=60,  # 默认重试延迟60秒
    task_max_retries=3,  # 最大重试次数3次
)

# 自动发现任务
celery_app.autodiscover_tasks(['tasks'])


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Worker启动时执行"""
    print("SoundVerse Celery worker ready")


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Worker关闭时执行"""
    print("SoundVerse Celery worker shutting down")


if __name__ == '__main__':
    celery_app.start()