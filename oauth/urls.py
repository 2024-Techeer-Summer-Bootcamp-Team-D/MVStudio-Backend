from django.urls import path
from . import views

urlpatterns = [
    path('/login/google', views.LoginGoogleView.as_view(), name='login_auth_google'),
    path('/login/google/callback', views.LoginGoogleCallbackView.as_view(), name='login_google_callback'),
    path('/youtube/<int:mv_id>', views.YoutubeUploadGoogleView.as_view(), name='youtube_auth'),
    path('/youtube/callback', views.YoutubeUploadGoogleCallbackView.as_view(), name='youtube_callback'),
    path('/youtube-channel', views.AuthYoutubeView.as_view(), name='youtube_channel'),
    path('/youtube-channel/callback', views.AuthYoutubeCallbackView.as_view(), name='youtube_channel_callback'),
]