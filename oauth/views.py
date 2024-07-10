from django.shortcuts import redirect
from django.urls import reverse
from rest_framework.views import APIView
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from django.conf import settings

class AuthYoutubeView(APIView):
    def get(self, request):
        # OAuth 2.0 플로우 설정
        client_config = {
            "web": {
                "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": "http://localhost:8000/oauth/youtube/callback/"
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=['https://www.googleapis.com/auth/youtube.readonly'],
            redirect_uri="http://localhost:8000/oauth/youtube/callback/"
        )

        # 인증 URL 생성 및 리디렉션
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        request.session['state'] = state
        return redirect(authorization_url)


class AuthYoutubeCallbackView(APIView):
    def get(self, request):
        state = request.session['state']
        client_config = {
            "web": {
                "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8000/oauth/youtube/callback/"]
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=['https://www.googleapis.com/auth/youtube.readonly'],
            state=state,
            redirect_uri="http://localhost:8000/oauth/youtube/callback/"
        )

        # 사용자 인증 코드 처리
        authorization_response = request.build_absolute_uri()
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials

        # YouTube API 클라이언트 생성
        youtube = build('youtube', 'v3', credentials=credentials)
        response = youtube.channels().list(
            mine=True,
            part='snippet'
        ).execute()

        # 유튜브 채널 URL 생성
        channel_url = "https://www.youtube.com/channel/" + response['items'][0]['id']

        # 프론트엔드로 리디렉션
        redirect_url = f"http://localhost:4137/edit?youtube_url={channel_url}"

        return redirect(redirect_url)