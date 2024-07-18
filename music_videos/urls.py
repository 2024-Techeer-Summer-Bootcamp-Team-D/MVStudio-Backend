# music_videos/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.MusicVideoView.as_view(), name='create_music_video'),
    path('', views.MusicVideoView.as_view(), name='music-video-detail'),
    path('/<int:music_video_id>', views.MusicVideoDetailView.as_view(), name='music-video-detail'),
    path('/<int:music_video_id>', views.MusicVideoDetailView.as_view(), name='delete-music-video'),
    path('/develop', views.MusicVideoDevelopView.as_view(), name='develop-music-video'),
    path('/genres', views.GenreListView.as_view(), name='genres-list'),
    path('/histories/<int:history_id>', views.HistoryUpdateView.as_view(), name='update-history'),
    path('/histories/<int:member_id>/<int:mv_id>', views.HistoryCreateView.as_view(), name='create-history'),
    path('/histories-list/<int:member_id>', views.HistoryDetailView.as_view(), name='history-detail'),
    path('/instruments', views.InstrumentListView.as_view(), name='instruments-list'),
    path('/lyrics', views.CreateLyricsView.as_view(), name='create_lyrics'),
    path('/searches', views.MusicVideoSearchView.as_view(), name='music-video-search'),
    path('/status/<str:task_id>', views.MusicVideoStatusView.as_view(), name='music-video-status'),
    path('/styles', views.StyleListView.as_view(), name='styles-list'),
]