# views.py
import boto3
from django.conf import settings

from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Member
from .serializers import MemberSerializer, MemberDetailSerializer, MemberLoginSerializer

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from datetime import datetime
import logging
import os

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
                        "code": "M001",
                        "status": 201,
                        "message": "회원가입 완료"
                    }
                }
            ),
            400: openapi.Response(
                description="회원가입 실패",
                examples={
                    "application/json": {
                        "code": "M002",
                        "status": 400,
                        "message": "이미 존재하는 로그인 ID입니다."
                    }
                }
            ),
        }
    )
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                response_data = {
                    "code": "A001",
                    "status": 201,
                    "message": "회원가입 완료"
                }
                logger.info(f'INFO {client_ip} {current_time} POST /members 201 signup success')
                return Response(response_data, status=201)
            except serializers.ValidationError as e:
                response_data = {
                    "code": "A002",
                    "status": 400,
                    "message": "이미 존재하는 로그인 ID입니다."
                }
                logger.warning(f'WARNING {client_ip} {current_time} POST /members 400 already existing')
                return Response(response_data, status=400)
        logger.warning(f'WARNING {client_ip} {current_time} POST /members 400 signup failed')
        return Response(serializer.errors, status=400)


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
                            "age": "integer",
                            "sex": "string",
                            "country": "string",
                            "code": "P001",
                            "HTTPstatus": 200,
                            "message": "회원 정보 조회 성공"
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="회원 정보가 없습니다.",
                examples={
                    "application/json": {
                        "code": "P002",
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
                "code": "P002",
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
        logger.info(f'INFO {client_ip} {current_time} GET /members 200 signup success')
        return Response(serializer.data, status=200)

    @swagger_auto_schema(
        operation_summary="회원 정보 수정 API",
        operation_description="이 API는 특정 회원의 정보를 수정하는 데 사용됩니다.",

    manual_parameters=[
            openapi.Parameter(
                'login_id',
                openapi.IN_FORM,
                description="Login ID",
                type=openapi.TYPE_STRING,
                required=False
            ),
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
                description="회원 정보 수정 완료",
                examples={
                    "application/json": {
                        "code": "P003",
                        "status": 200,
                        "message": "회원 정보 수정 완료"
                    }
                }
            ),
            404: openapi.Response(
                description="회원 정보가 없습니다.",
                examples={
                    "application/json": {
                        "code": "P002",
                        "status": 404,
                        "message": "회원 정보가 없습니다."
                    }
                }
            ),
            400: openapi.Response(
                description="유효하지 않은 데이터입니다.",
                examples={
                    "application/json": {
                        "code": "P004",
                        "status": 400,
                        "message": "유효하지 않은 데이터입니다."
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
                "code": "P002",
                "status": 404,
                "message": "회원 정보가 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} PATCH /members 404 does not existing')
            return Response(response_data, status=404)
        data = request.data.copy()
        image_file = data['profile_image']

        if image_file:
            content_type = image_file.content_type
            s3 = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME,
                              aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
            s3_bucket = settings.AWS_STORAGE_BUCKET_NAME
            # 파일 이름을 member_id로 구별
            file_extension = os.path.splitext(image_file.name)[1]  # 파일 확장자 추출
            s3_key = f"profiles/{member_id}{file_extension}"

            s3.upload_fileobj(image_file, s3_bucket, s3_key, ExtraArgs={
                'ContentType': content_type
            })


            image_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}{s3_key}"

            data['profile_image'] = image_url
            serializer = MemberDetailSerializer(instance=member, data=data, partial=True)

        else:
            serializer = MemberDetailSerializer(instance=member, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            response_data = {
                "code": "P003",
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
            200: openapi.Response(
                description="로그인 성공",
                examples={
                    "application/json": {
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
            response_data = {
                "code": "A001",
                "status": 200,
                "message": "로그인 성공"
            }
            logger.info(f'INFO {client_ip} {current_time} POST /members/login 200 login success')
            return Response(response_data, status=200)
        response_data = {
            "code": "A002_1",
            "status": 400,
            "message": "로그인 실패"
        }
        logger.warning(f'WARNING {client_ip} {current_time} POST /members/login 400 login failed')
        return Response(response_data, status=400)