from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from drf_yasg.utils import swagger_auto_schema

from rest_framework.views import APIView

from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import get_user_model

from .mixins import PublicApiMixin
from .utils import social_user_get_or_create
from .services import google_get_access_token, google_get_user_info
from .authenticate import jwt_login

User = get_user_model()

@swagger_auto_schema(auto_schema=None)
class LoginGoogleView(PublicApiMixin, APIView):
    def get(self, request, *args, **kwargs):
        app_key = settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY
        scope = "https://www.googleapis.com/auth/userinfo.email " + \
                "https://www.googleapis.com/auth/userinfo.profile"

        redirect_uri = settings.BASE_BACKEND_URL + "api/v1/oauth/login/google/callback"
        google_auth_api = "https://accounts.google.com/o/oauth2/v2/auth"

        response = redirect(
            f"{google_auth_api}?client_id={app_key}&response_type=code&redirect_uri={redirect_uri}&scope={scope}"
        )

        return response

@swagger_auto_schema(auto_schema=None)
class LoginGoogleCallbackView(PublicApiMixin, APIView):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code')
        google_token_api = "https://oauth2.googleapis.com/token"

        access_token = google_get_access_token(google_token_api, code)
        user_data = google_get_user_info(access_token=access_token)

        profile_data = {
            'username': user_data['email'],
            'first_name': user_data.get('given_name', ''),
            'last_name': user_data.get('family_name', ''),
            'nickname': user_data.get('nickname', ''),
            'name': user_data.get('name', ''),
            'image': user_data.get('picture', None),
            'path': "google",
        }

        member, is_exist = social_user_get_or_create(**profile_data)
        if(is_exist):
            response = redirect(settings.BASE_FRONTEND_URL+'auth/register')
        else:
            response = redirect(settings.BASE_FRONTEND_URL+'main')
        response = jwt_login(response=response, user=member)
        return response


@swagger_auto_schema(auto_schema=None)
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


@swagger_auto_schema(auto_schema=None)
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