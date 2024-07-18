# music_videos/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('/develop', views.MusicVideoDevelopView.as_view(), name='develop-music-video'),
    path('/lyrics', views.CreateLyricsView.as_view(), name='create-lyrics'),
    path('', views.MusicVideoView.as_view(), name='music-video'),
    path('/status/<str:task_id>', views.MusicVideoStatusView.as_view(), name='music-video-status'),
    path('/<int:mv_id>', views.MusicVideoDetailView.as_view(), name='music-video-detail'),
    path('/searches', views.MusicVideoSearchView.as_view(), name='music-video-search'),
    path('/genres', views.GenreListView.as_view(), name='genres-list'),
    path('/instruments', views.InstrumentListView.as_view(), name='instruments-list'),
    path('/styles', views.StyleListView.as_view(), name='styles-list'),
    path('/histories/<int:history_id>', views.HistoryUpdateView.as_view(), name='update-history'),
    path('/histories/<str:username>/<int:mv_id>', views.HistoryCreateView.as_view(), name='create-history'),
    path('/histories-list/<str:username>', views.HistoryDetailView.as_view(), name='history-detail'),
    path('/graph/daily/<int:member_id>', views.MusicVideoDailyGraphView.as_view(), name='music-video-graph-daily'),
    path('/graph/gender/<int:member_id>', views.MusicVideoGenderGraphView.as_view(), name='music-video-graph-gender'),
    path('/graph/country/<int:member_id>', views.MusicVideoCountryGraphView.as_view(), name='music-video-graph-country'),
    path('/graph/age/<int:member_id>', views.MusicVideoAgeGraphView.as_view(), name='music-video-graph-age'),
]