from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue  # kombu에서 Queue와 Exchange 임포트
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# 비트 스케줄 설정
app.conf.beat_schedule = {
    'reset-recently-viewed-every-week': {
        'task': 'music_videos.tasks.hot_music_video_scheduled',
        'schedule': crontab(minute=0, hour=0, day_of_week='monday'),  # 매주 월요일 자정에 실행
    },
    'rebuild_elasticsearch_index': {
        'task': 'music_videos.tasks.rebuild_elasticsearch_index',
        'schedule': crontab(minute=0, hour='*'),  # 매시간 정각에 실행
    },
}

# 큐 설정
app.conf.task_queues = (
    Queue('music_queue', Exchange('music', type='direct'), routing_key='music_queue'),
    Queue('video_queue', Exchange('videos', type='direct'), routing_key='video_queue'),
    Queue('final_queue', Exchange('final', type='direct'), routing_key='final_queue'),
)

# 라우팅 설정
app.conf.task_routes = {
    'tasks.suno_music': {'queue': 'music_queue'},
    'tasks.create_video': {'queue': 'video_queue'},
    'tasks.mv_create': {'queue': 'final_queue'},
}

# 기본 큐 설정
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'

logger = logging.getLogger(__name__)
logger.info("Current Celery Beat schedule: %s", app.conf.beat_schedule)