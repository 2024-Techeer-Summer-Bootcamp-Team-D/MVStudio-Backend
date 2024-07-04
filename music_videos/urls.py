# music_videos/urls.py

from django.urls import path
from . import views


urlpatterns = [
    path('lyrics/', views.CreateLyricsView.as_view(), name='create_lyrics'),
]