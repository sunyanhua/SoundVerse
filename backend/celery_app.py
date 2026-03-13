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
    include=['backend.tasks'],
)

# 配置Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟
    task_soft_time_limit=25 * 60,
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_reject_on_worker_lost=True,
)

# 自动发现任务
celery_app.autodiscover_tasks(['backend'])


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