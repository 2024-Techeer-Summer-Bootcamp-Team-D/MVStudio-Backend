# __init__.py

from __future__ import absolute_import, unicode_literals

# 이 코드를 추가합니다
from .celery import app as celery_app

__all__ = ('celery_app',)
