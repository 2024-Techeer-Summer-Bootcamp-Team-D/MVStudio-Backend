from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils.translation import gettext_lazy as _

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from oauth.authenticate import generate_access_token, jwt_login
from oauth.mixins import ApiAuthMixin, PublicApiMixin

from .models import Member, Country
from music_videos.models import History, MusicVideo
from music_videos.s3_utils import upload_file_to_s3
from .serializers import MemberDetailSerializer, CountrySerializer, RegisterSerializer

import jwt
from datetime import datetime
import logging
import os
import sys

# 현재 파일의 경로를 가져옵니다
current_dir = os.path.dirname(os.path.abspath(__file__))
# 상위 폴더의 경로를 구합니다
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
# 상위 폴더의 경로를 sys.path에 추가합니다
sys.path.insert(0, parent_dir)

User = get_user_model()

logger = logging.getLogger(__name__)

class UserCreateApi(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_summary="회원가입 API",
        operation_description="Create a new user",
        request_body=RegisterSerializer,
        responses={
            200: "User created successfully",
            409: "Request Body Error"
        }
    )
    def post(self, request, *args, **kwargs):
        """
        회원가입 api

        """
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid(raise_exception=True):
            return Response({
                "message": "Request Body Error"
            }, status=status.HTTP_409_CONFLICT)

        user = serializer.save()

        response = Response(status=status.HTTP_200_OK)
        response = jwt_login(response=response, user=user)
        return response


class LoginApi(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_summary="로그인 API",
        operation_description="Log in with username and password",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Password')
            },
            required=['username', 'password']
        ),
        responses={
            200: "Login successful",
            400: "username/password required or wrong password",
            404: "User not found"
        }
    )
    def post(self, request, *args, **kwargs):
        """
        username 과 password를 가지고 login 시도
        key값 : username, password
        """
        username = request.data.get('username')
        password = request.data.get('password')

        if (username is None) or (password is None):
            return Response({
                "message": "username/password required"
            }, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(username=username).first()
        if user is None:
            return Response({
                "message": "유저를 찾을 수 없습니다"
            }, status=status.HTTP_404_NOT_FOUND)
        if not user.check_password(password):
            return Response({
                "message": "wrong password"
            }, status=status.HTTP_400_BAD_REQUEST)

        response = Response(status=status.HTTP_200_OK)
        return jwt_login(response, user)

class LogoutApi(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_summary="로그아웃 API",
        operation_description="Log out and delete refresh token cookie",
        responses={
            202: "Logout success"
        }
    )
    def post(self, request):
        """
        클라이언트 refreshtoken 쿠키를 삭제함으로 로그아웃처리
        """
        response = Response({
            "message": "Logout success"
        }, status=status.HTTP_202_ACCEPTED)
        response.delete_cookie('refreshtoken')

        return response

class MemberDetailView(ApiAuthMixin, APIView):
    parser_classes = (MultiPartParser, FormParser)
    @swagger_auto_schema(
        operation_summary="회원 정보 조회 API",
        operation_description="Retrieve member details by username",
        responses={
            200: MemberDetailSerializer,
            404: "회원 정보가 없습니다."
        }
    )
    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = User.objects.filter(username=username).first()
        except Member.DoesNotExist:
            response_data = {
                "code": "P001_1",
                "status": 404,
                "message": "회원 정보가 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} GET /members 404 does not existing')
            return Response(response_data, status=404)
        serializer = MemberDetailSerializer(member)
        response_data = {
            "data": serializer.data,
            "code": "P001",
            "status": 200,
            "message": "회원 정보 조회 성공"
        }
        logger.info(f'INFO {client_ip} {current_time} GET /members 200 info check success')
        return Response(response_data, status=200)

    @swagger_auto_schema(
        operation_summary="회원 정보 수정 API",
        operation_description="Update member details by username",
        request_body=MemberDetailSerializer,
        responses={
            200: "회원 정보 수정 완료",
            404: "회원 정보가 없습니다.",
            500: "s3 이미지 업로드 실패."
        }
    )


    def patch(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = User.objects.filter(username=username).first()
        except Member.DoesNotExist:
            response_data = {
                "code": "P002_2",
                "status": 404,
                "message": "회원 정보가 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} PATCH /members 404 does not existing')
            return Response(response_data, status=404)

        data = request.data.copy()
        image_file = data.get('profile_image', None)

        if image_file:
            content_type = image_file.content_type

            # 파일 이름을 username로 구별
            file_extension = os.path.splitext(image_file.name)[1]  # 파일 확장자 추출
            s3_key = f"profiles/{username}{file_extension}"
            image_url = upload_file_to_s3(image_file, s3_key, ExtraArgs={
                "ContentType": content_type,
            })

            if not image_url:
                response_data = {
                    "code": "P002_3",
                    "status": 500,
                    "message": "s3 이미지 업로드 실패."
                }
                logger.warning(f'WARNING {client_ip} {current_time} PATCH /members 500 does not existing')
                return Response(response_data, status=500)

            data['profile_image'] = image_url
        else:
            data['profile_image'] = member.profile_image

        serializer = MemberDetailSerializer(instance=member, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            response_data = {
                "code": "P002",
                "status": 200,
                "message": "회원 정보 수정 완료"
            }
            logger.info(f'INFO {client_ip} {current_time} PATCH /members/{username} 200 update success')
            return Response(response_data, status=200)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @swagger_auto_schema(
        operation_summary="회원 탈퇴 API",
        operation_description="Delete the current logged-in user",
        responses={
            204: "Delete user success",
            400: "passwords do not match"
        }
    )
    def delete(self, request, *args, **kwargs):
        """
        현재 로그인 된 유저 삭제
        소셜 로그인 유저는 바로 삭제.
        일반 회원가입 유저는 비밀번호 입력 후 삭제.
        """
        user = request.user
        signup_path = user.profile.signup_path

        if signup_path == "kakao" or signup_path == "google":
            user.delete()
            return Response({
                "message": "Delete user success"
            }, status=status.HTTP_204_NO_CONTENT)

        if not check_password(request.data.get("password"), user.password):
            raise serializers.ValidationError(
                _("passwords do not match")
            )

        user.delete()

        return Response({
            "message": "Delete user success"
        }, status=status.HTTP_204_NO_CONTENT)
class CountryListView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="국가 리스트 조회 API",
        operation_description="이 API는 사용자의 국가를 선택할 수 있도록 국가 리스트를 제공하는 기능을 합니다.",
        responses={
            200: openapi.Response(
                description="국가 리스트 조회 성공",
                examples={
                    "application/json": {
                        "code": "P003",
                        "status": 200,
                        "message": "국가 리스트 조회 성공",
                        "data": {
                            "name": "string",
                            "code": "P003",
                            "HTTPstatus": 200,
                            "message": "국가 리스트 조회 성공"
                        }
                    }
                }
            ),
            500: openapi.Response(
                description="국가 리스트 조회 실패",
                examples={
                    "application/json": {
                        "code": "P003_1",
                        "status": 500,
                        "message": "국가 리스트 조회 실패"
                    }
                }
            ),
        }
    )
    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            countries = Country.objects.all()
            serializer = CountrySerializer(countries, many=True)
            response_data = {
                "code": "P003",
                "status": 200,
                "message": "국가 리스트 조회 성공",
                "data": serializer.data
            }
            logger.info(f'INFO {client_ip} {current_time} GET /country_list 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "P003_1",
                "status": 500,
                "message": "국가 리스트 조회 실패"
            }
            logger.warning(f'WARNING {client_ip} {current_time} GET /country_list 500 failed')
            return Response(response_data, status=500)


class RefreshJWTtoken(APIView):
    @swagger_auto_schema(
        operation_summary="Access Token 재발급 API",
        operation_description="Refresh JWT token",
        responses={
            200: openapi.Response(
                description="New access token",
                examples={
                    'application/json': {
                        'access_token': 'new_access_token'
                    }
                }
            ),
            403: "Authentication credentials were not provided or expired refresh token",
            400: "User not found or inactive"
        }
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refreshtoken')

        if refresh_token is None:
            return Response({
                "message": "Authentication credentials were not provided."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = jwt.decode(
                refresh_token, settings.REFRESH_TOKEN_SECRET, algorithms=['HS256']
            )
        except:
            return Response({
                "message": "expired refresh token, please login again."
            }, status=status.HTTP_403_FORBIDDEN)

        user = User.objects.filter(id=payload['user_id']).first()

        if user is None:
            return Response({
                "message": "user not found"
            }, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({
                "message": "user is inactive"
            }, status=status.HTTP_400_BAD_REQUEST)

        access_token = generate_access_token(user)

        return Response(
            {
                'access_token': access_token,
            }
        )

class MemberDailyGraphView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="사용자 채널 날짜별 조회수 통계 조회 API",
        operation_description="사용자의 채널을 날짜별 조회수를 통계로 분석할 수 있습니다.",
        responses={
            200: openapi.Response(
                description="사용자 채널 날짜별 조회수 통계 조회 성공",
                examples={
                    "application/json": [
                        {
                        "code": "G001_1",
                        "status": 200,
                        "message": "사용자 채널 개수가 0개입니다.",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "",
                            "popular_mv_views": 0,
                            "daily_views": [
                                {
                                    "daily_views_date": "yyyy-mm-dd",
                                    "daily_views_views": 0,
                                },
                                {
                                    "daily_views_date": "yyyy-mm-dd",
                                    "daily_views_views": 0,
                                },
                                {
                                    "daily_views_date": "yyyy-mm-dd",
                                    "daily_views_views": 0,
                                },
                            ]
                        }
                        },
                        {
                        "code": "G001",
                        "status": 200,
                        "message": "사용자 채널 날짜별 조회수 통계 조회 성공",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "string",
                            "popular_mv_views": 0,
                            "daily_views": [
                            {
                                "daily_views_date": "yyyy-mm-dd",
                                "daily_views_views": 0,
                            },
                            {
                                "daily_views_date": "yyyy-mm-dd",
                                "daily_views_views": 0,
                            },
                            {
                                "daily_views_date": "yyyy-mm-dd",
                                "daily_views_views": 0,
                            },
                            ],
                            }
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="사용자 채널 날짜별 조회수 통계 조회 실패",
                examples={
                    "application/json": {
                        "code": "G001_2",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )

    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(username=username)
        except Member.DoesNotExist:
            response_data = {
                "code": "G001_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} /music_videos 404 Member Not Found')
            return Response(response_data, status=404)

        member_name = member.nickname
        music_videos = MusicVideo.objects.filter(username=member)

        start_date = member.created_at.date()
        end_date = datetime.now().date()
        date_range = (end_date - start_date).days + 1
        daily_views = {(start_date + timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(date_range)}

        history_data = (History.objects
                        .filter(mv_id__in=music_videos)
                        .annotate(day=TruncDate('created_at'))
                        .values('day')
                        .annotate(views=Count('id'))
                        .order_by('day'))

        for data in history_data:
            daily_views[data['day'].strftime('%Y-%m-%d')] = data['views']

        if not music_videos.exists():
            response_data = {
                "code": "G001_1",
                "status": 200,
                "message": "사용자 채널 개수가 0개입니다.",
                "member_name": member_name,
                "total_mv": 0,
                "total_views": 0,
                "popular_mv_subject": "",
                "popular_mv_views": 0,
                "daily_views": [
                    {
                        "daily_views_date": date,
                        "daily_views_views": views
                    } for date, views in daily_views.items()
                ],
            }
            logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 No music videos')
            return Response(response_data, status=200)

        total_mv = music_videos.count()
        total_views = 0
        popular_mv_subject = []
        popular_mv_views = 0

        for music_video in music_videos:
            total_views += music_video.views
            if music_video.views >= popular_mv_views and music_video.views != 0:
                popular_mv_subject.append(music_video.subject)
                popular_mv_views = music_video.views

        response_data = {
            "code": "G001",
            "status": 200,
            "message": "사용자 채널 날짜별 조회수 통계 조회 성공",
            "member_name": member_name,
            "total_mv": total_mv,
            "total_views": total_views,
            "popular_mv_subject": popular_mv_subject,
            "popular_mv_views": popular_mv_views,
            "daily_views": [
                    {
                        "daily_views_date": date,
                        "daily_views_views": views,
                    } for date, views in daily_views.items()
                ],
        }
        logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class MemberGenderGraphView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="사용자 채널 성별 통계 조회 API",
        operation_description="사용자의 채널을 성별 통계로 분석할 수 있습니다.",
        responses={
            200: openapi.Response(
                description="사용자 채널 성별 통계 조회 성공",
                examples={
                    "application/json": [
                        {
                        "code": "G002_1",
                        "status": 200,
                        "message": "사용자 채널 개수가 0개입니다.",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "",
                            "popular_mv_views": 0,
                            "gender_list": [
                                {
                                    "gender_name": "string",
                                    "gender_number": 0,
                                },
                                ]
                        }
                        },
                        {
                        "code": "G002",
                        "status": 200,
                        "message": "사용자 채널 성별 통계 조회 성공",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "string",
                            "popular_mv_views": 0,
                            "gender_list": [
                            {
                                "gender_name": "string",
                                "gender_number": 0,
                            },
                            ],
                            }
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="사용자 채널 성별 통계 조회 실패",
                examples={
                    "application/json": {
                        "code": "G002_2",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )
    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(username=username)
        except Member.DoesNotExist:
            response_data = {
                "code": "G002_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} /music_videos 404 Member Not Found')
            return Response(response_data, status=404)

        member_name = member.nickname
        music_videos = MusicVideo.objects.filter(username=member.username).values_list('id', flat=True)

        gender_list = [
            {'gender_name': 'Male', 'gender_number': 0},
            {'gender_name': 'Female', 'gender_number': 0},
        ]

        processed_viewers = set()

        for video in music_videos:
            viewers = History.objects.filter(mv_id=video).values_list('username', flat=True)
            for viewer in viewers:
                if viewer in processed_viewers:
                    continue
                processed_viewers.add(viewer)
                member_gender = Member.objects.get(username=viewer).sex
                if member_gender == "M":
                    gender_list[0]['gender_number'] += 1
                elif member_gender == "F":
                    gender_list[1]['gender_number'] += 1

        if not music_videos.exists():
            response_data = {
                "code": "G002_1",
                "status": 200,
                "message": "사용자 채널 개수가 0개입니다.",
                "member_name": member_name,
                "total_mv": 0,
                "total_views": 0,
                "popular_mv_subject": "",
                "popular_mv_views": 0,
                "gender_list": [
                    {
                        "gender_name": item['gender_name'],
                        "gender_number": item['gender_number']
                    } for item in gender_list
                ],
            }
            logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 No music videos')
            return Response(response_data, status=200)

        total_mv = music_videos.count()
        total_views = 0
        popular_mv_subject = []
        popular_mv_views = 0

        for music_video in music_videos:
            mv_views = MusicVideo.objects.get(id=music_video).views
            total_views += mv_views
            if mv_views >= popular_mv_views and mv_views != 0:
                popular_mv_subject.append(MusicVideo.objects.get(id=music_video).subject)
                popular_mv_views = mv_views

        response_data = {
            "code": "G002",
            "status": 200,
            "message": "사용자 채널 성별 통계 조회 성공",
            "member_name": member_name,
            "total_mv": total_mv,
            "total_views": total_views,
            "popular_mv_subject": popular_mv_subject,
            "popular_mv_views": popular_mv_views,
            "gender_list": [
                    {
                        "gender_name": item['gender_name'],
                        "gender_number": item['gender_number']
                    } for item in gender_list
                ],
        }
        logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class MemberCountryGraphView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="사용자 채널 국가별 통계 조회 API",
        operation_description="사용자의 채널을 국가별 통계로 분석할 수 있습니다.",
        responses={
            200: openapi.Response(
                description="사용자 채널 국가별 통계 조회 성공",
                examples={
                    "application/json": [
                        {
                        "code": "G003_1",
                        "status": 200,
                        "message": "사용자 채널 개수가 0개입니다.",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "",
                            "popular_mv_views": 0,
                            "country_list": [
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                ]
                        }
                        },
                        {
                        "code": "G003",
                        "status": 200,
                        "message": "사용자 채널 국가별 통계 조회 성공",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "string",
                            "popular_mv_views": 0,
                            "country_list": [
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                            ],
                            }
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="사용자 채널 국가별 통계 조회 실패",
                examples={
                    "application/json": {
                        "code": "G003_2",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )
    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(username=username)
        except Member.DoesNotExist:
            response_data = {
                "code": "G003_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} /music_videos 404 Member Not Found')
            return Response(response_data, status=404)

        member_name = member.nickname
        music_videos = MusicVideo.objects.filter(username=member.username).values_list('id', flat=True)

        countries = Country.objects.filter(is_deleted=False)
        country_list = []
        for country in countries:
            country_list.append({
                'country_id': country.id,
                'country_name': country.name,
                'country_views': 0
            })

        processed_viewers = set()

        for video in music_videos:
            viewers = History.objects.filter(mv_id=video).values_list('username', flat=True)
            for viewer in viewers:
                if viewer in processed_viewers:
                    continue
                processed_viewers.add(viewer)
                member_country = Member.objects.get(username=viewer).country
                for country in country_list:
                    if member_country.name == country['country_name']:
                        country['country_views'] += 1

        if not music_videos.exists():
            response_data = {
                "code": "G003_1",
                "status": 200,
                "message": "사용자 채널 개수가 0개입니다.",
                "member_name": member_name,
                "total_mv": 0,
                "total_views": 0,
                "popular_mv_subject": "",
                "popular_mv_views": 0,
                "country_list": [
                    {
                        'country_id': item['country_id'],
                        'country_name': item['country_name'],
                        'country_views': item['country_views']
                    } for item in country_list
                ],
            }
            logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 No music videos')
            return Response(response_data, status=200)

        total_mv = music_videos.count()
        total_views = 0
        popular_mv_subject = []
        popular_mv_views = 0

        for music_video in music_videos:
            mv_views = MusicVideo.objects.get(id=music_video).views
            total_views += mv_views
            if mv_views >= popular_mv_views and mv_views != 0:
                popular_mv_subject.append(MusicVideo.objects.get(id=music_video).subject)
                popular_mv_views = mv_views

        response_data = {
            "code": "G003",
            "status": 200,
            "message": "사용자 채널 국가별 통계 조회 성공",
            "member_name": member_name,
            "total_mv": total_mv,
            "total_views": total_views,
            "popular_mv_subject": popular_mv_subject,
            "popular_mv_views": popular_mv_views,
            "country_list": [
                {
                    'country_id': item['country_id'],
                    'country_name': item['country_name'],
                    'country_views': item['country_views']
                } for item in country_list
            ],
        }
        logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class MemberAgeGraphView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="사용자 채널 연령별 통계 조회 API",
        operation_description="사용자의 채널을 연령별 통계로 분석할 수 있습니다.",
        responses={
            200: openapi.Response(
                description="사용자 채널 연령별 통계 조회 성공",
                examples={
                    "application/json": [
                        {
                            "code": "G004_1",
                            "status": 200,
                            "message": "사용자 채널 개수가 0개입니다.",
                            "data": {
                                "member_name": "string",
                                "total_mv": 0,
                                "total_views": 0,
                                "popular_mv_subject": "",
                                "popular_mv_views": 0,
                                "age_list": [
                                    {
                                        "age_group": "string",
                                        "age_views": 0
                                    },
                                ]
                            }
                        },
                        {
                            "code": "G004",
                            "status": 200,
                            "message": "사용자 채널 연령별 통계 조회 성공",
                            "data": {
                                "member_name": "string",
                                "total_mv": 0,
                                "total_views": 0,
                                "popular_mv_subject": "string",
                                "popular_mv_views": 0,
                                "age_list": [
                                    {
                                        "age_group": "string",
                                        "age_views": 0
                                    },
                                ]
                            }
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="사용자 채널 연령별 통계 조회 실패",
                examples={
                    "application/json": {
                        "code": "G004_2",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )
    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(username=username)
        except Member.DoesNotExist:
            response_data = {
                "code": "G004_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} /music_videos 404 Member Not Found')
            return Response(response_data, status=404)

        member_name = member.nickname
        music_videos = MusicVideo.objects.filter(username=member.username).values_list('id', flat=True)

        age_list = [
            {'age_group': '10s and under', 'age_views': 0},
            {'age_group': '20s', 'age_views': 0},
            {'age_group': '30s', 'age_views': 0},
            {'age_group': '40s', 'age_views': 0},
            {'age_group': '50s and above', 'age_views': 0}
        ]

        current_year = datetime.now().year
        processed_viewers = set()

        for video in music_videos:
            viewers = History.objects.filter(mv_id=video).values_list('username', flat=True)
            for viewer in viewers:
                if viewer in processed_viewers:
                    continue
                processed_viewers.add(viewer)
                viewer_member = Member.objects.get(username=viewer)
                birth_date = viewer_member.birthday
                birth_year = birth_date.year
                age = current_year - birth_year
                if age < 20:
                    age_list[0]['age_views'] += 1
                elif age < 30:
                    age_list[1]['age_views'] += 1
                elif age < 40:
                    age_list[2]['age_views'] += 1
                elif age < 50:
                    age_list[3]['age_views'] += 1
                else:
                    age_list[4]['age_views'] += 1

        if not music_videos.exists():
            response_data = {
                "code": "G004_1",
                "status": 200,
                "message": "사용자 채널 개수가 0개입니다.",
                "member_name": member_name,
                "total_mv": 0,
                "total_views": 0,
                "popular_mv_subject": "",
                "popular_mv_views": 0,
                "age_list": [
                    {
                        'age_group': item['age_group'],
                        'age_views': item['age_views']
                    } for item in age_list
                ],
            }
            logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 No music videos')
            return Response(response_data, status=200)

        total_mv = music_videos.count()
        total_views = 0
        popular_mv_subject = []
        popular_mv_views = 0

        for music_video in music_videos:
            mv_views = MusicVideo.objects.get(id=music_video).views
            total_views += mv_views
            if mv_views >= popular_mv_views and mv_views != 0:
                popular_mv_subject.append(MusicVideo.objects.get(id=music_video).subject)
                popular_mv_views = mv_views

        response_data = {
            "code": "G004",
            "status": 200,
            "message": "사용자 채널 연령별 통계 조회 성공",
            "member_name": member_name,
            "total_mv": total_mv,
            "total_views": total_views,
            "popular_mv_subject": popular_mv_subject,
            "popular_mv_views": popular_mv_views,
            "age_list": [
                {
                    'age_group': item['age_group'],
                    'age_views': item['age_views']
                } for item in age_list
            ],
        }
        logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)

