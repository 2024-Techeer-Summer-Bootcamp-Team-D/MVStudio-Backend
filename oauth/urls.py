from django.urls import path
from . import views

urlpatterns = [
    path('login/google', views.LoginGoogleView.as_view(), name='login_auth_google'),
    path('login/google/callback', views.LoginGoogleCallbackView.as_view(), name='login_google_callback'),
    path('youtube', views.AuthYoutubeView.as_view(), name='youtube_auth'),
    path('instagram', views.AuthYoutubeView.as_view(), name='instagram_auth'),
    path('youtube/callback', views.AuthYoutubeCallbackView.as_view(), name='youtube_callback'),
    path('instagram/callback', views.AuthYoutubeCallbackView.as_view(), name='instagram_callback'),
]