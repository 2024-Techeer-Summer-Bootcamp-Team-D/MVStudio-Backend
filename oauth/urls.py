from django.urls import path
from . import views


urlpatterns = [
    path('youtube', views.AuthYoutubeView.as_view(), name='youtube_auth'),
    path('instagram', views.AuthYoutubeView.as_view(), name='instagram_auth'),
    path('youtube/callback', views.AuthYoutubeCallbackView.as_view(), name='youtube_callback'),
    path('instagram/callback', views.AuthYoutubeCallbackView.as_view(), name='instagram_callback'),
]