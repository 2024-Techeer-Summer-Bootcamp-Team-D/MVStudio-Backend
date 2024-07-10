# celery.py

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
import logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'reset-recently-viewed-every-minute': {
        'task': 'music_videos.tasks.hot_music_video_scheduled',
        'schedule': crontab(minute=0, hour=0),
    },
}

logger = logging.getLogger(__name__)
logger.info("Current Celery Beat schedule: %s", app.conf.beat_schedule)