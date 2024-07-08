# music_videos/urls.py

from django.urls import path
from . import views


urlpatterns = [
    path('lyrics/', views.CreateLyricsView.as_view(), name='create_lyrics'),
    path('', views.MusicVideo.as_view(), name='create_music_video'),
    path('genres/', views.GenreListView.as_view(), name='genres-list'),
    path('instruments/', views.InstrumentListView.as_view(), name='instruments-list'),
]