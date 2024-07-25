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


class MemberInfoView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="본인 회원 Info 조회 API",
        operation_description="Retrieve the username of the current logged-in user",
        responses={
            200: openapi.Response(
                description="본인 회원 Info 조회 성공",
                examples={
                    "application/json": {
                        "username": "string",
                        "credits": "string",
                        "code": "A004",
                        "status": 200,
                        "message": "본인 회원 Info 조회 성공",
                    }
                }
            ),
            404: openapi.Response(
                description="본인 회원 Info 조회 실패",
                examples={
                    "application/json": {
                        "code": "A004_1",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )

    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        member = request.user
        if not member:
            response_data = {
                "code": "A004_1",
                "status": 404,
                "message": "회원정보를 찾을 수 없습니다.",
            }
            logger.warning(f'[{current_time}] {client_ip} GET /members 404 Info check failed')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

        response_data = {
            "username": member.username,
            "credits": request.user.credits,
            "code": "A004",
            "status": 200,
            "message": "본인 회원 Info 조회 성공",
        }
        logger.info(f'[{current_time}] {client_ip} GET /members 200 Info check success')
        return Response(response_data, status=200)

class UserCreateApi(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_summary="회원가입 API",
        operation_description="Create a new user",
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response(
                description="회원가입 성공",
                examples={
                    "application/json": {
                        "access_token": "string",
                        "code": "A001",
                        "status": 201,
                        "message": "회원가입 성공",
                    }
                }
            ),
            400: openapi.Response(
                description="회원가입 실패",
                examples={
                    "application/json": {
                        "code": "A001_1",
                        "status": 400,
                        "message": "회원가입 실패"
                    }
                }
            )
        }
    )

    def post(self, request, *args, **kwargs):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            response_data = {
                "code": "A001_1",
                "status": 400,
                "message": "회원가입 실패"
            }
            logger.warning(f'[{current_time}] {client_ip} POST /members 400 Signup failed: {serializer.errors}')
            return Response(data=response_data, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        response = Response()
        response_token = jwt_login(response=response, user=user)
        response_data = {
            "access_token": response.data.get('access_token'),
            "code": "A001",
            "status": 201,
            "message": "회원가입 성공",
        }
        logger.info(f'[{current_time}] {client_ip} POST /members 201 Signup successful for user id: {user.id}')
        return Response(data=response_data, status=status.HTTP_201_CREATED)


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
            201: openapi.Response(
                description="로그인 성공",
                examples={
                    "application/json": {
                        "access_token": "string",
                        "code": "A002",
                        "status": 201,
                        "message": "로그인 성공",
                    }
                }
            ),
            400: openapi.Response(
                description="잘못된 요청",
                examples={
                    "application/json": [
                        {
                            "code": "A002_1",
                            "status": 400,
                            "message": "사용자 이름/비밀번호를 작성해주세요."
                        },
                        {
                            "code": "A002_2",
                            "status": 400,
                            "message": "잘못된 비밀번호입니다."
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="로그인 실패",
                examples={
                    "application/json": {
                        "code": "A002_3",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        """
        username 과 password를 가지고 login 시도
        key값 : username, password
        """
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            response_data = {
                "code": "A002_1",
                "status": 400,
                "message": "사용자 이름/비밀번호를 작성해주세요."
            }
            logger.warning(f'[{current_time}] {client_ip} POST /members 400 Login failed: {response_data["message"]}')
            return Response(data=response_data, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(username=username).first()
        if user is None:
            response_data = {
                "code": "A002_3",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(f'[{current_time}] {client_ip} POST /members 404 Member information not found: {response_data["message"]}')
            return Response(data=response_data, status=status.HTTP_404_NOT_FOUND)

        if not user.check_password(password):
            response_data = {
                "code": "A002_2",
                "status": 400,
                "message": "잘못된 비밀번호입니다."
            }
            logger.warning(f'[{current_time}] {client_ip} POST /members 400 Incorrect password: {response_data["message"]}')
            return Response(data=response_data, status=status.HTTP_400_BAD_REQUEST)

        response = Response()
        response_token = jwt_login(response=response, user=user)
        response_data = {
            "access_token": response.data.get('access_token'),
            "code": "A002",
            "status": 201,
            "message": "로그인 성공"
        }
        logger.info(f'[{current_time}] {client_ip} POST /members 201 Login successful')
        return Response(data=response_data, status=status.HTTP_201_CREATED)


class LogoutApi(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_summary="로그아웃 API",
        operation_description="Log out and delete refresh token cookie",
        responses={
            202: openapi.Response(
                description="로그아웃 성공",
                examples={
                    "application/json": {
                        "code": "A003",
                        "status": 202,
                        "message": "로그아웃 성공",
                    }
                }
            ),
        }
    )
    def post(self, request):
        """
        클라이언트 refreshtoken 쿠키를 삭제함으로 로그아웃처리
        """
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response_data = {
            "code": "A003",
            "status": 202,
            "message": "로그아웃 성공",
        }
        response = Response(response_data, status=status.HTTP_202_ACCEPTED)
        response.delete_cookie('refreshtoken')

        logger.info(f'[{current_time}] {client_ip} POST /members/logout 202 Logout successful')
        return response

class MemberDetailView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="회원 정보 조회 API",
        operation_description="Retrieve member details by username",
        responses={
            200: openapi.Response(
                description="회원 정보 조회 성공",
                examples={
                    "application/json": {
                        "code": "A006",
                        "status": 200,
                        "message": "회원 정보 조회 성공",
                        "data": {
                            "username": "string",
                            "email": "string",
                            "name": "string",
                            "nickname": "string",
                            "profile_image": "string",
                            "comment": "string",
                            "country": "string",
                            "birthday": "string",
                            "sex": "string",
                            "youtube_account": "string",
                            "instagram_account": "string",
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="회원 정보 조회 실패",
                examples={
                    "application/json": {
                        "code": "A006_1",
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

        member = User.objects.filter(username=username).first()

        if not member:
            response_data = {
                "code": "A006_1",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(f'[{current_time}] {client_ip} GET /members 404 Member information not found')
            return Response(response_data, status=404)

        serializer = MemberDetailSerializer(member)
        response_data = {
            "code": "A006",
            "status": 200,
            "message": "회원 정보 조회 성공",
            "data": serializer.data,
        }
        logger.info(f'[{current_time}] {client_ip} GET /members 200 Member information retrieval successful')
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
                'country_id',
                openapi.IN_FORM,
                description="Country ID",
                type=openapi.TYPE_INTEGER,
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
                        "code": "A007",
                        "status": 200,
                        "message": "회원 정보 수정 성공"
                    }
                }
            ),
            404: openapi.Response(
                description="회원 정보를 찾을 수 없습니다.",
                examples={
                    "application/json": {
                        "code": "A007_1",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            ),
        }
    )

    def patch(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        member = User.objects.filter(username=username).first()

        if not member:
            response_data = {
                "code": "A007_1",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(f'[{current_time}] {client_ip} PATCH /members 404 Member information not found')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

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
            data['profile_image'] = image_url
        else:
            data['profile_image'] = member.profile_image

        serializer = MemberDetailSerializer(instance=member, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            response_data = {
                "data": serializer.data,
                "code": "A007",
                "status": 200,
                "message": "회원 정보 수정 완료"
            }
            logger.info(f'[{current_time}] {client_ip} PATCH /members/{username} 200 Update successful')
            return Response(response_data, status=status.HTTP_200_OK)

        logger.warning(f'[{current_time}] {client_ip} PATCH /members/{username} 400 Update failed: {serializer.errors}')
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @swagger_auto_schema(
        operation_summary="회원 탈퇴 API",
        operation_description="Delete the current logged-in user",
        responses={
            204: openapi.Response(
                description="회원 탈퇴 성공",
                examples={
                    "application/json": {
                        "code": "A008",
                        "status": 204,
                        "message": "회원 탈퇴 성공",
                    }
                }
            ),
            400: openapi.Response(
                description="회원 탈퇴 실패",
                examples={
                    "application/json": {
                        "code": "A008",
                        "status": 400,
                        "message": "비밀번호를 잘못 입력했습니다."
                    }
                }
            ),
        }
    )
    def delete(self, request, *args, **kwargs):
        """
        현재 로그인 된 유저 삭제
        소셜 로그인 유저는 바로 삭제.
        일반 회원가입 유저는 비밀번호 입력 후 삭제.
        """
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = request.user
        signup_path = user.profile.signup_path

        if signup_path == "kakao" or signup_path == "google":
            user.delete()
            response_data = {
                "code": "A008",
                "status": 204,
                "message": "회원 탈퇴 성공",
            }
            logger.info(f'[{current_time}] {client_ip} DELETE /members/{user.username} 204 Member deletion successful')
            return Response(data=response_data, status=status.HTTP_204_NO_CONTENT)

        if not check_password(request.data.get("password"), user.password):
            raise serializers.ValidationError(
                _("passwords do not match")
            )

        user.delete()
        response_data = {
            "code": "A008",
            "status": 204,
            "message": "회원 탈퇴 성공",
        }
        logger.info(f'[{current_time}] {client_ip} DELETE /members/{user.username} 204 Member deletion successful')
        return Response(data=response_data, status=status.HTTP_204_NO_CONTENT)

class CountryListView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="국가 리스트 조회 API",
        operation_description="이 API는 사용자의 국가를 선택할 수 있도록 국가 리스트를 제공하는 기능을 합니다.",
        responses={
            200: openapi.Response(
                description="국가 리스트 조회 성공",
                examples={
                    "application/json": {
                        "code": "A010",
                        "status": 200,
                        "message": "국가 리스트 조회 성공",
                        "data": {
                            "id": 0,
                            "name": "string",
                        }
                    }
                }
            ),
            500: openapi.Response(
                description="국가 리스트 조회 실패",
                examples={
                    "application/json": {
                        "code": "A010_1",
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
                "code": "A010",
                "status": 200,
                "message": "국가 리스트 조회 성공",
                "data": serializer.data
            }
            logger.info(f'[{current_time}] {client_ip} GET /countries 200 Country list retrieval successful')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "A010_1",
                "status": 500,
                "message": "국가 리스트 조회 실패"
            }
            logger.error(f'[{current_time}] {client_ip} GET /countries 500 Country list retrieval failed: {str(e)}')
            return Response(response_data, status=500)


class RefreshJWTtoken(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_summary="Access Token 재발급 API",
        operation_description="Refresh JWT token",
        responses={
            200: openapi.Response(
                description="Access Token 재발급 성공",
                examples={
                    "application/json": {
                        "access_token": "string",
                        "code": "A005",
                        "status": 200,
                        "message": "Access Token 재발급 성공"
                    }
                }
            ),
            400: openapi.Response(
                description="회원 정보를 찾을 수 없습니다.",
                examples={
                    "application/json": [
                        {
                            "code": "A005_1",
                            "status": 400,
                            "message": "회원 정보를 찾을 수 없습니다."
                        },
                        {
                            "code": "A005_2",
                            "status": 400,
                            "message": "사용자의 계정이 비활성화되었습니다."
                        }
                    ]
                }
            ),
            403: openapi.Response(
                description="Access Token 재발급 실패",
                examples={
                    "application/json": [
                        {
                            "code": "A005_3",
                            "status": 403,
                            "message": "인증 자격이 증명되지 않았습니다."
                        },
                        {
                            "code": "A005_4",
                            "status": 403,
                            "message": "리프레시 토큰이 만료되었습니다."
                        }
                    ]
                }
            ),
        }
    )
    def post(self, request, *args, **kwargs):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        refresh_token = request.COOKIES.get('refreshtoken')

        if refresh_token is None:
            response_data = {
                "code": "A005_3",
                "status": 403,
                "message": "인증 자격이 증명되지 않았습니다."
            }
            logger.warning(f'[{current_time}] {client_ip} POST /refresh_token 403 Authentication credentials were not provided')
            return Response(data=response_data, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = jwt.decode(
                refresh_token, settings.REFRESH_TOKEN_SECRET, algorithms=['HS256']
            )
        except:
            response_data = {
                "code": "A005_4",
                "status": 403,
                "message": "리프레시 토큰이 만료되었습니다."
            }
            logger.warning(f'[{current_time}] {client_ip} POST /refresh_token 403 Refresh token has expired')
            return Response(data=response_data, status=status.HTTP_403_FORBIDDEN)

        user = User.objects.filter(id=payload['user_id']).first()

        if user is None:
            response_data = {
                "code": "A005_1",
                "status": 400,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(f'[{current_time}] {client_ip} POST /members 400 Member information not found')
            return Response(data=response_data, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            response_data = {
                "code": "A005_2",
                "status": 400,
                "message": "사용자의 계정이 비활성화되었습니다."
            }
            logger.warning(f'[{current_time}] {client_ip} POST /members 400 User account is deactivated')
            return Response(data=response_data, status=status.HTTP_400_BAD_REQUEST)

        access_token = generate_access_token(user)

        response_data = {
            'access_token': access_token,
            "code": "A005",
            "status": 200,
            "message": "Access Token 재발급 성공"
        }
        logger.info(f'[{current_time}] {client_ip} POST /refresh_token 200 Access token reissued successfully')
        return Response(data=response_data, status=status.HTTP_200_OK)



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
            201: openapi.Response(
                description='결제 페이지로 리다이렉트',
                examples={
                    "application/json": {
                        "code": "A009",
                        "status": 201,
                        "message": "결제 요청 성공",
                    }
                }
            ),
            400: openapi.Response(
                description='결제 요청 실패',
                examples={
                    "application/json": {
                        "code": "A009_1",
                        "status": 400,
                        "message": "결제 요청 실패"
                    }
                }
            )
        }
    )
    def post(self, request, *args, **kwargs):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        credits = request.data.get('credits')
        price = request.data.get('price')
        user = request.user

        kakao_pay = KakaoPayClient()

        # 카카오페이 결제준비 API 호출
        success, ready_process = kakao_pay.ready(user, credits, price)

        if success:
            response_data = {
                "code": "A009",
                "status": 201,
                "message": "결제 요청 성공",
                "next_redirect_pc_url": (ready_process["next_redirect_pc_url"])
            }
            logger.info(f'[{current_time}] {client_ip} POST /payment 201 Payment request successful')
            return Response(data=response_data, status=status.HTTP_201_CREATED)
        else:
            response_data = {
                 "code": "A009_1",
                 "status": 400,
                 "message": "결제 요청 실패"
            }
            logger.warning(f'[{current_time}] {client_ip} POST /payment 400 Payment request failed')
            return Response(data=response_data, status=status.HTTP_400_BAD_REQUEST)
