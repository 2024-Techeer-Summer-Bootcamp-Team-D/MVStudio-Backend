# celery.py

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# 브로커와 백엔드 설정
app.conf.broker_url = 'pyamqp://guest@localhost//'
app.conf.result_backend = 'redis://localhost'

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'reset-recently-viewed-every-minute': {
        'task': 'music_videos.tasks.hot_music_video_scheduled',
        'schedule': crontab(minute=0, hour=0),
    },
    'rebuild_elasticsearch_index': {
        'task': 'music_videos.tasks.rebuild_elasticsearch_index',
        'schedule': crontab(hour=0, minute=0),  # 매일 자정에 실행
    },
}

app.conf.update(
    task_routes={
        'tasks.suno_music': {'queue': 'music_queue'},
        'tasks.create_video': {'queue': 'video_queue'},
        'tasks.mv_create': {'queue': 'final_queue'},
    },
    task_queues={
        'music_queue': {
            'exchange': 'music',
            'exchange_type': 'direct',
            'binding_key': 'music_queue',
        },
        'video_queue': {
            'exchange': 'videos',
            'exchange_type': 'direct',
            'binding_key': 'video_queue',
        },
        'final_queue': {
            'exchange': 'final',
            'exchange_type': 'direct',
            'binding_key': 'final_queue',
        },
    }
)


logger = logging.getLogger(__name__)
logger.info("Current Celery Beat schedule: %s", app.conf.beat_schedule)