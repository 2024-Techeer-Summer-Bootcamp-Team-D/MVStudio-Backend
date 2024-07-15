# views.py
import boto3
from django.conf import settings

from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Member, Country
from .serializers import MemberSerializer, MemberDetailSerializer, MemberLoginSerializer, CountrySerializer


from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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

from music_videos.s3_utils import upload_file_to_s3

logger = logging.getLogger(__name__)


class MemberSignUpView(APIView):
    @swagger_auto_schema(
        operation_summary="회원가입 API",
        operation_description="이 API는 신규 사용자를 등록하는 데 사용됩니다.",
        request_body=MemberSerializer,
        responses={
            201: openapi.Response(
                description="회원가입 완료",
                examples={
                    "application/json": {
                        "id" : 0,
                        "username": "string",
                        "code": "A001",
                        "status": 201,
                        "message": "회원가입 완료"
                    }
                }
            ),
            400: openapi.Response(
                description="잘못된 요청",
                examples={
                    "application/json": [
                        {
                            "code": "A001_1",
                            "status": 400,
                            "message": "유효하지 않은 country ID입니다."
                        },
                        {
                            "code": "A001_2",
                            "status": 400,
                            "message": "유효하지 않은 데이터입니다."
                        }
                    ]
                }
            ),
            409: openapi.Response(
                description="회원가입 실패",
                examples={
                    "application/json": {
                        "code": "A001_3",
                        "status": 409,
                        "message": "이미 존재하는 로그인 ID입니다."
                    }
                }
            ),
        }
    )
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        login_id = request.data.get('login_id')
        country_id = request.data.get('country')
        if not Country.objects.filter(id=country_id).exists():
            response_data = {
                "code": "A001_1",
                "status": 400,
                "message": "유효하지 않은 country ID입니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} POST /members 400 invalid country id')
            return Response(response_data, status=400)
        
        # 중복된 login_id 확인
        if Member.objects.filter(login_id=login_id).exists():
            existing_member = Member.objects.get(login_id=login_id)
            response_data = {
                "code": "A001_3",
                "status": 409,
                "message": "이미 존재하는 로그인 ID입니다.",
            }
            logger.warning(f'WARNING {client_ip} {current_time} POST /members 409 already existing')
            return Response(response_data, status=200)


        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            member = serializer.save()
            response_data = {
                "id": member.id,
                "username": member.nickname,
                "code": "A001",
                "status": 201,
                "message": "회원가입 완료"
            }
            logger.info(f'INFO {client_ip} {current_time} POST /members 201 signup success')
            return Response(response_data, status=201)
        else:
            response_data = {
                "code": "A001_2",
                "status": 400,
                "message": "유효하지 않은 데이터입니다."
            }
        logger.warning(f'WARNING {client_ip} {current_time} POST /members 400 signup failed')
        return Response(response_data, status=400)


class MemberDetailView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    @swagger_auto_schema(
        operation_summary="회원 정보 조회 API",
        operation_description="이 API는 특정 회원의 정보를 조회하는 데 사용됩니다.",
        responses={
            200: openapi.Response(
                description="회원 정보 조회 성공",
                examples={
                    "application/json": {
                        "code": "P001",
                        "status": 200,
                        "message": "회원 정보 조회 성공",
                        "data": {
                            "login_id": "string",
                            "nickname": "string",
                            "sex": "string",
                            "comment": "string",
                            "country": "string",
                            "birthday": "string",
                            "profile_image": "string",
                            "youtube_account": "string",
                            "instagram_account": "string",
                            "code": "P001",
                            "HTTPstatus": 200,
                            "message": "회원 정보 조회 성공"
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="회원 정보 조회 실패",
                examples={
                    "application/json": {
                        "code": "P001_1",
                        "status": 404,
                        "message": "회원 정보가 없습니다."
                    }
                }
            ),
        }
    )

    def get(self, request, member_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(id=member_id)
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
            "code": "P001",
            "status": 200,
            "message": "회원 정보 조회 성공"
        }
        logger.info(f'INFO {client_ip} {current_time} GET /members 200 info check success')
        return Response(serializer.data, status=200)

    @swagger_auto_schema(
        operation_summary="회원 정보 수정 API",
        operation_description="이 API는 특정 회원의 정보를 수정하는 데 사용됩니다.",

    manual_parameters=[
            openapi.Parameter(
                'nickname',
                openapi.IN_FORM,
                description="Nickname",
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

    def patch(self, request, member_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(id=member_id)
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

            # 파일 이름을 member_id로 구별
            file_extension = os.path.splitext(image_file.name)[1]  # 파일 확장자 추출
            s3_key = f"profiles/{member_id}{file_extension}"
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
            logger.info(f'INFO {client_ip} {current_time} PATCH /members/{member_id} 200 update success')
            return Response(response_data, status=200)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberLoginView(APIView):
    @swagger_auto_schema(
        operation_summary="로그인 API",
        operation_description="이 API는 사용자 로그인을 처리하는 데 사용됩니다.",
        request_body=MemberLoginSerializer,
        responses={
            201: openapi.Response(
                description="로그인 성공",
                examples={
                    "application/json": {
                        "id": 0,
                        "username": "string",
                        "code": "A002",
                        "status": 201,
                        "message": "로그인 성공"
                    }
                }
            ),
            400: openapi.Response(
                description="로그인 실패",
                examples={
                    "application/json": {
                        "code": "A002_1",
                        "status": 400,
                        "message": "로그인 실패"
                    }
                }
            ),
        }
    )
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        serializer = MemberLoginSerializer(data=request.data)
        if serializer.is_valid():
            member = Member.objects.get(login_id=serializer.validated_data['login_id'])
            response_data = {
                "id": member.id,
                "username": member.nickname,
                "code": "A002",
                "status": 201,
                "message": "로그인 성공"
            }
            logger.info(f'INFO {client_ip} {current_time} POST /members/login 201 login success')
            return Response(response_data, status=201)
        response_data = {
            "code": "A002_1",
            "status": 400,
            "message": "로그인 실패"
        }
        logger.warning(f'WARNING {client_ip} {current_time} POST /members/login 400 login failed')
        return Response(response_data, status=400)


class CountryListView(APIView):
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