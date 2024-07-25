from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from drf_yasg.utils import swagger_auto_schema

from rest_framework.views import APIView

from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import get_user_model

from .mixins import PublicApiMixin, ApiAuthMixin
from .utils import social_user_get_or_create
from .services import google_get_access_token, google_get_user_info, google_upload_youtube
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

        redirection_uri = settings.BASE_BACKEND_URL + "api/v1/oauth/login/google/callback"

        access_token = google_get_access_token(google_token_api, code, redirection_uri)
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
class YoutubeUploadGoogleView(ApiAuthMixin, APIView):
    def post(self, request, *args, **kwargs):
        app_key = settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY
        scope = "https://www.googleapis.com/auth/youtube " + \
                "https://www.googleapis.com/auth/youtube.readonly " + \
                "https://www.googleapis.com/auth/youtube.upload"

        mv_id = kwargs.get('mv_id')

        redirect_uri = settings.BASE_BACKEND_URL + f"api/v1/oauth/youtube/callback"
        google_auth_api = "https://accounts.google.com/o/oauth2/v2/auth"

        response = redirect(
            f"{google_auth_api}?client_id={app_key}&response_type=code&redirect_uri={redirect_uri}&scope={scope}&state={mv_id}"
        )

        return response

@swagger_auto_schema(auto_schema=None)
class YoutubeUploadGoogleCallbackView(PublicApiMixin, APIView):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code')
        mv_id = request.GET.get('state')
        google_token_api = "https://oauth2.googleapis.com/token"

        redirection_uri = settings.BASE_BACKEND_URL + "api/v1/oauth/youtube/callback"

        access_token = google_get_access_token(google_token_api, code, redirection_uri)
        google_upload_youtube(access_token=access_token, mv_id=mv_id)
        response = redirect(settings.BASE_FRONTEND_URL+'main')

        return response


@swagger_auto_schema(auto_schema=None)
class AuthYoutubeView(PublicApiMixin, APIView):
    def get(self, request):
        redirect_uri = settings.BASE_BACKEND_URL + "api/v1/oauth/youtube-channel/callback"

        # OAuth 2.0 플로우 설정
        client_config = {
            "web": {
                "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=[
                'https://www.googleapis.com/auth/youtube.readonly',
                'https://www.googleapis.com/auth/userinfo.email',
                'openid',
                'https://www.googleapis.com/auth/userinfo.profile'
            ],
        )
        flow.redirect_uri = redirect_uri

        # 인증 URL 생성 및 리디렉션
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        request.session['state'] = state
        return redirect(authorization_url)


@swagger_auto_schema(auto_schema=None)
class AuthYoutubeCallbackView(PublicApiMixin, APIView):
    def get(self, request):
        state = request.session.get('state')
        if not state:
            return Response({"error": "State parameter is missing from session."}, status=status.HTTP_400_BAD_REQUEST)

        redirect_uri = settings.BASE_BACKEND_URL + "api/v1/oauth/youtube-channel/callback"

        client_config = {
            "web": {
                "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=[
                'https://www.googleapis.com/auth/youtube.readonly',
                'https://www.googleapis.com/auth/userinfo.email',
                'openid',
                'https://www.googleapis.com/auth/userinfo.profile'
            ],
            state=state,
        )
        flow.redirect_uri = redirect_uri

        # 사용자 인증 코드 처리
        authorization_response = request.build_absolute_uri()
        try:
            flow.fetch_token(authorization_response=authorization_response)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        credentials = flow.credentials

        try:
            # YouTube API 클라이언트 생성
            youtube = build('youtube', 'v3', credentials=credentials)
            response = youtube.channels().list(
                mine=True,
                part='snippet'
            ).execute()

            # 유튜브 채널 URL 생성
            channel_url = "https://www.youtube.com/channel/" + response['items'][0]['id']
        except Exception as e:
            return Response({"error": "Failed to retrieve YouTube channel information."}, status=status.HTTP_400_BAD_REQUEST)

        # 프론트엔드로 리디렉션
        redirect_url = f"{settings.BASE_FRONTEND_URL}users?youtube_url={channel_url}"
        return redirect(redirect_url)