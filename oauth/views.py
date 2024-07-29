from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import googleapiclient

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import get_user_model

from .mixins import PublicApiMixin, ApiAuthMixin
from .utils import social_user_get_or_create
from .services import google_get_access_token, google_get_user_info, google_upload_youtube
from .authenticate import jwt_login
from music_videos.models import MusicVideo
import requests
from io import BytesIO


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
        #         scope = "https://www.googleapis.com/auth/youtube " + \
        #                 "https://www.googleapis.com/auth/youtube.readonly " + \
        #                 "https://www.googleapis.com/auth/youtube.upload"
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


@swagger_auto_schema(auto_schema=None)
class YoutubeUploadGoogleView(ApiAuthMixin, APIView):
    def get(self, request, mv_id):
        mv = MusicVideo.objects.get(id=mv_id)

        if (str(mv.username) != str(request.user.username)):
            response_data = {
                "code": "O002_1",
                "status": 403,
                "message": "본인 소유의 뮤직비디오가 아닙니다."
            }
            return Response(response_data, status=status.HTTP_403_FORBIDDEN)

        redirect_uri = settings.BASE_BACKEND_URL + "api/v1/oauth/youtube/callback"

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
                'https://www.googleapis.com/auth/youtube.upload',
                'https://www.googleapis.com/auth/userinfo.email',
                'openid',
                'https://www.googleapis.com/auth/youtube.readonly',
                'https://www.googleapis.com/auth/youtube',
                'https://www.googleapis.com/auth/userinfo.profile'
            ],
        )
        flow.redirect_uri = redirect_uri

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        request.session['state'] = state
        request.session['mv_id'] = mv_id

        return redirect(authorization_url)

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
@swagger_auto_schema(auto_schema=None)
class YoutubeUploadGoogleCallbackView(APIView):
    def get(self, request):
        state = request.session.get('state')
        mv_id = request.session.get('mv_id')

        if not state:
            return Response({"error": "State parameter is missing from session."}, status=status.HTTP_400_BAD_REQUEST)

        redirect_uri = settings.BASE_BACKEND_URL + "api/v1/oauth/youtube/callback"

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
                'https://www.googleapis.com/auth/youtube.upload',
                'https://www.googleapis.com/auth/userinfo.email',
                'openid',
                'https://www.googleapis.com/auth/youtube.readonly',
                'https://www.googleapis.com/auth/youtube',
                'https://www.googleapis.com/auth/userinfo.profile'
            ],
            state=state,
        )
        flow.redirect_uri = redirect_uri

        authorization_response = request.build_absolute_uri()
        try:
            flow.fetch_token(authorization_response=authorization_response)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        credentials = flow.credentials

        # credentials를 세션에 저장
        request.session['credentials'] = credentials_to_dict(credentials)
        frontend_redirect_url = f"{settings.BASE_FRONTEND_URL}upload?mv-id={mv_id}"

        return redirect(frontend_redirect_url)

def download_video(video_url):
    response = requests.get(video_url, stream=True)
    response.raise_for_status()  # 요청이 성공적으로 완료되지 않으면 예외 발생
    return BytesIO(response.content)

class UploadVideoView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_description="Upload a video to YouTube",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING, description='Title of the video'),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description='Description of the video'),
                'tags': openapi.Schema(type=openapi.TYPE_STRING, description='Comma-separated keywords for the video'),
                'privacyStatus': openapi.Schema(type=openapi.TYPE_STRING, description='Privacy status of the video'),
                'thumbnail': openapi.Schema(type=openapi.TYPE_FILE, description='Thumbnail image file'),
            },
            required=['mv_id']  # 필수 항목 명시
        )
    )
    def post(self, request, mv_id):
        credentials = request.session.get('credentials')
        if not credentials:
            response_data = {
                "code": "O003_2",
                "status": 403,
                "message": "구글 계정 권한이 없습니다."
            }
            return Response(response_data, status=status.HTTP_403_FORBIDDEN)

        credentials = Credentials(**credentials)

        youtube = build('youtube', 'v3', credentials=credentials)
        mv = MusicVideo.objects.get(id=mv_id)

        if (str(mv.username) != str(request.user.username)):
            response_data = {
                "code": "O003_1",
                "status": 403,
                "message": "본인 소유의 뮤직비디오가 아닙니다."
            }
            return Response(response_data, status=status.HTTP_403_FORBIDDEN)

        title = request.data.get('title', mv.subject)
        description = request.data.get('description')
        category = '22'
        tags = request.data.get('tags')
        privacy_status = request.data.get('privacyStatus', 'public')
        thumbnail = request.FILES.get('thumbnail')

        video_data = download_video(mv.mv_file)

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category
            },
            'status': {
                'privacyStatus': privacy_status
            }
        }

        media_body = MediaIoBaseUpload(video_data, mimetype='video/*', chunksize=-1, resumable=True)

        insert_request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media_body
        )

        try:
            response = None
            while response is None:
                task_status, response = insert_request.next_chunk()
                if 'id' in response:
                    video_id = response['id']
                    try:
                        if thumbnail:
                            # 썸네일 업로드
                            thumbnail_data = BytesIO(thumbnail.read())
                            youtube.thumbnails().set(
                                videoId=video_id,
                                media_body=MediaIoBaseUpload(thumbnail_data, mimetype=thumbnail.content_type)
                            ).execute()
                    except googleapiclient.errors.HttpError as e:
                        error_content = e.resp.content
                        response_data = {
                            "code": "O003_4",
                            "status": 200,
                            "message": f"뮤직비디오 업로드는 성공하였으나, 권한문제로 인하여 썸네일 업로드를 실패하였습니다. error: {error_content.decode()}"
                        }
                        return Response(response_data, status=status.HTTP_200_OK)
                    response_data = {
                        "code": "O003",
                        "status": 200,
                        "message": "뮤직비디오가 성공적으로 업로드되었습니다."
                    }
                    return Response(response_data,status=status.HTTP_200_OK)
        except Exception as e:
            response_data = {
                "code": "O003_3",
                "status": 500,
                "message": f"뮤직비디오 업로드를 실패하였습니다. error: {str(e)}"
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = {
            "code": "O003_3",
            "status": 500,
            "message": f"뮤직비디오 업로드를 실패하였습니다."
        }
        return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)