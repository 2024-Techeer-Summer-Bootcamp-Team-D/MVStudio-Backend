from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _
from django.shortcuts import redirect

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from oauth.authenticate import generate_access_token, jwt_login
from oauth.mixins import ApiAuthMixin, PublicApiMixin

from .models import Member, Country
from music_videos.s3_utils import upload_file_to_s3
from .serializers import MemberDetailSerializer, CountrySerializer, RegisterSerializer
from .payment import KakaoPayClient

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

class MemberUsernameView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="본인 회원 username 조회 API",
        operation_description="Retrieve the username of the current logged-in user",
        responses={
            200: MemberDetailSerializer,
            404: "회원 정보가 없습니다."
        }
    )
    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            members = User.objects.all()
        except Member.DoesNotExist:
            response_data = {
                "code": "M001_1",
                "status": 404,
                "message": "회원 정보가 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} GET /members 404 does not existing')
            return Response(response_data, status=404)
        serializer = MemberDetailSerializer(members, many=True)

        response_data = {
            "username": request.user.username,
            "code": "M001",
            "status": 200,
            "message": "회원 정보 조회 성공",
        }
        logger.info(f'INFO {client_ip} {current_time} GET /members 200 info check success')
        return Response(response_data, status=200)

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

    parser_classes = (MultiPartParser, FormParser)
    @swagger_auto_schema(
        operation_summary="회원 정보 수정 API",
        operation_description="Update member details by username",
        manual_parameters=[
            openapi.Parameter(
                'nickname',
                openapi.IN_FORM,
                description="Nickname",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'email',
                openapi.IN_FORM,
                description="Email",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'profile_image',
                openapi.IN_FORM,
                description="Profile image file",
                type=openapi.TYPE_FILE,
                required=False
            ),
            openapi.Parameter(
                'sex',
                openapi.IN_FORM,
                description="Sex",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'comment',
                openapi.IN_FORM,
                description="Comment",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'country',
                openapi.IN_FORM,
                description="Country",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'birthday',
                openapi.IN_FORM,
                description="Birthday",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'youtube_account',
                openapi.IN_FORM,
                description="YouTube account",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'instagram_account',
                openapi.IN_FORM,
                description="Instagram account",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="회원 정보 수정 성공",
                examples={
                    "application/json": {
                        "code": "P002",
                        "status": 200,
                        "message": "회원 정보 수정 성공"
                    }
                }
            ),
            404: openapi.Response(
                description="회원 정보가 없습니다.",
                examples={
                    "application/json": {
                        "code": "P002_2",
                        "status": 404,
                        "message": "회원 정보가 없습니다."
                    }
                }
            ),
            400: openapi.Response(
                description="유효하지 않은 데이터입니다.",
                examples={
                    "application/json": {
                        "code": "P002_1",
                        "status": 400,
                        "message": "유효하지 않은 데이터입니다."
                    }
                }
            ),
            500: openapi.Response(
                description="s3 이미지 업로드 실패",
                examples={
                    "application/json": {
                        "code": "P002_3",
                        "status": 500,
                        "message": "s3 이미지 업로드 실패"
                    }
                }
            ),
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


class RefreshJWTtoken(PublicApiMixin, APIView):
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



class KakaoPayment(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_description="카카오페이 결제 요청",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'credits': openapi.Schema(type=openapi.TYPE_INTEGER, description='크레딧 수'),
                'price': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT, description='가격')
            }
        ),
        responses={
            302: openapi.Response(
                description='결제 페이지로 리다이렉트',
                examples={
                    'application/json': {
                        "message": "결제 요청 성공"
                    }
                }
            ),
            400: openapi.Response(
                description='결제 요청 실패',
                examples={
                    'application/json': {
                        "message": "결제 요청 실패"
                    }
                }
            )
        }
    )
    def post(self, request, *args, **kwargs):
        credits = request.data.get('credits')
        price = request.data.get('price')
        user = request.user

        kakao_pay = KakaoPayClient()

        # 카카오페이 결제준비 API 호출
        success, ready_process = kakao_pay.ready(user, credits, price)

        if success:
            response_data = {
                "message": "결제 요청 성공"
            }
            response = redirect(ready_process["next_redirect_pc_url"])
            return response
        else:
            response_data = {
                "message": "결제 요청 실패"
            }
            redirect_uri = settings.BASE_FRONTEND_URL + f"payment?status=fail"
            response = redirect(redirect_uri)
            return response


