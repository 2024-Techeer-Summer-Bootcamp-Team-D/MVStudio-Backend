# tasks.py

from celery import shared_task
from music_videos.models import MusicVideo
from config.celery import app
import logging

logger = logging.getLogger(__name__)
@app.task
def hot_music_video_scheduled():
    MusicVideo.objects.update(recently_viewed=0)
    print("All MusicVideo recently_viewed columns have been reset to 0.")
    logger.info("All MusicVideo recently_viewed columns have been reset to 0.")
